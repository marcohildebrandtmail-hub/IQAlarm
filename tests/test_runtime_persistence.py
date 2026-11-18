"""Persistence concurrency and failure regressions using isolated HA adapters."""

import asyncio
from copy import deepcopy

import pytest
from safety_support import core, local_runtime, runtime_module


async def spin_until(predicate):
    """Observe test-only task state without adding hooks to production code."""
    async with asyncio.timeout(1):
        while not predicate():  # noqa: ASYNC110
            await asyncio.sleep(0)


def test_one_write_coalesces_hundreds_of_simultaneous_requests(tmp_path):
    async def scenario():
        runtime = local_runtime(tmp_path)
        await asyncio.gather(*(runtime.persist() for _ in range(250)))
        await runtime.hass.drain()
        assert len(runtime.store.writes) == 1
        assert runtime._persistence_saved == runtime._persistence_requested == 250
        assert not runtime._persistence_waiters

    asyncio.run(scenario())


def test_changes_during_write_are_saved_next_and_waiters_finish_per_snapshot(tmp_path):
    async def scenario():
        runtime = local_runtime(tmp_path)
        original = runtime.store.async_save
        releases = [asyncio.Event(), asyncio.Event()]
        snapshots = []
        concurrent, maximum = 0, 0

        async def delayed(**kwargs):
            nonlocal concurrent, maximum
            index = len(snapshots)
            snapshots.append(deepcopy(kwargs))
            concurrent += 1
            maximum = max(maximum, concurrent)
            try:
                await releases[index].wait()
                await original(**kwargs)
            finally:
                concurrent -= 1

        runtime.store.async_save = delayed
        first = asyncio.create_task(runtime.persist())
        await spin_until(lambda: len(snapshots) == 1)
        runtime.engine.set_profile("armed_night", 100)
        runtime.engine.feed("binary_sensor.contact", True, 101)
        runtime.engine.feed("binary_sensor.motion", True, 102)
        runtime.dispatcher.outputs["siren.test"] = {"kind": "siren", "until": 500}
        runtime.external.state["queue"] = [{"id": "test-alarm", "operation": "start"}]
        later = [asyncio.create_task(runtime.persist()) for _ in range(100)]
        await spin_until(lambda: runtime._persistence_requested == 101)
        releases[0].set()
        await spin_until(lambda: len(snapshots) == 2)
        await first
        assert not any(task.done() for task in later)
        assert snapshots[0]["state"]["profile_id"] is None
        assert snapshots[0]["outputs"] == {}
        releases[1].set()
        await asyncio.gather(*later)
        await runtime.hass.drain()
        assert maximum == 1 and len(snapshots) == 2
        assert runtime.store.state["profile_id"] == "armed_night"
        assert runtime.store.state["external_monitor"]["queue"][0]["id"] == "test-alarm"
        assert "siren.test" in runtime.store.outputs
        restored = core(runtime.config)
        restored.restore(runtime.store.state, 103)
        assert restored.confirmed and restored.latched

    asyncio.run(scenario())


def test_wait_limit_does_not_cancel_writer_or_turn_lock_contention_into_errors(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(runtime_module, "_PERSISTENCE_FLUSH_WAIT", 0.01)

    async def scenario():
        runtime = local_runtime(tmp_path)
        await runtime.storage_lock.acquire()
        await asyncio.gather(*(runtime._flush_persistence() for _ in range(40)))
        assert not runtime._persistence_task.done()
        assert runtime.store.writes == []
        assert not runtime._persistence_waiters
        assert not any(event.kind == "runtime_error" for event in runtime.engine.events)
        runtime.storage_lock.release()
        await runtime.hass.drain()
        assert len(runtime.store.writes) == 1
        assert runtime._persistence_saved == 40

    asyncio.run(scenario())


def test_cancelled_caller_does_not_cancel_another_callers_write(tmp_path):
    async def scenario():
        runtime = local_runtime(tmp_path)
        await runtime.storage_lock.acquire()
        first = asyncio.create_task(runtime.persist())
        second = asyncio.create_task(runtime.persist())
        await spin_until(lambda: len(runtime._persistence_waiters) == 2)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert not runtime._persistence_task.done()
        runtime.storage_lock.release()
        await second
        await runtime.hass.drain()
        assert len(runtime.store.writes) == 1
        assert not runtime._persistence_waiters

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "error", [OSError("disk busy"), TimeoutError(), runtime_module.HomeAssistantError("busy")]
)
def test_real_failures_retry_without_new_events_and_log_one_incident(tmp_path, monkeypatch, error):
    monkeypatch.setattr(runtime_module, "_PERSISTENCE_RETRY_SECONDS", 0.001)
    monkeypatch.setattr(runtime_module, "_PERSISTENCE_RETRY_MAX", 0.002)

    async def scenario():
        runtime = local_runtime(tmp_path)
        original = runtime.store.async_save
        attempts = 0

        async def flaky(**kwargs):
            nonlocal attempts
            attempts += 1
            if attempts <= 3:
                raise error
            await original(**kwargs)

        runtime.store.async_save = flaky
        results = await asyncio.gather(
            *(runtime.persist() for _ in range(30)), return_exceptions=True
        )
        assert all(isinstance(result, type(error)) for result in results)
        await asyncio.wait_for(runtime.hass.drain(), 1)
        faults = [event for event in runtime.engine.events if event.kind == "runtime_error"]
        assert attempts == 4 and len(runtime.store.writes) == 1
        assert len(faults) == 1 and type(error).__name__ in faults[0].reason
        assert any(event.kind == "persistence_recovered" for event in runtime.engine.events)
        assert any(event["kind"] == "runtime_error" for event in runtime.store.state["events"])
        assert runtime._persistence_saved == runtime._persistence_requested
        assert not runtime._persistence_waiters and not runtime._persistence_failed

    asyncio.run(scenario())


def test_slow_write_is_not_cancelled_and_does_not_create_a_self_sustaining_save_loop(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(runtime_module, "_PERSISTENCE_SLOW_WRITE", 0.01)

    async def scenario():
        runtime = local_runtime(tmp_path)
        original = runtime.store.async_save
        release = asyncio.Event()

        async def delayed(**kwargs):
            await release.wait()
            await original(**kwargs)

        runtime.store.async_save = delayed
        caller = asyncio.create_task(runtime.persist())
        await spin_until(lambda: runtime._persistence_failed)
        assert not caller.done()
        release.set()
        await caller
        await asyncio.wait_for(runtime.hass.drain(), 1)
        assert len(runtime.store.writes) == 1
        assert not runtime._persistence_failed

    asyncio.run(scenario())


def test_shutdown_saves_latest_state_after_a_pending_write(tmp_path):
    async def scenario():
        runtime = local_runtime(tmp_path)
        original = runtime.store.async_save
        release, started = asyncio.Event(), asyncio.Event()
        attempts = 0

        async def delayed(**kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                started.set()
                await release.wait()
            await original(**kwargs)

        runtime.store.async_save = delayed
        caller = asyncio.create_task(runtime.persist())
        await started.wait()
        runtime.engine.set_profile("armed_night", 100)
        stopping = asyncio.create_task(runtime.stop())
        await spin_until(lambda: runtime._persistence_requested == 2)
        release.set()
        await asyncio.gather(caller, stopping)
        await runtime.hass.drain()
        assert runtime.store.state["profile_id"] == "armed_night"
        assert len(runtime.store.writes) == 2
        assert runtime._persistence_task.done()
        assert not runtime._persistence_waiters

    asyncio.run(scenario())


def test_shutdown_wakes_a_retry_and_does_not_wait_for_the_backoff(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime_module, "_PERSISTENCE_RETRY_SECONDS", 30)

    async def scenario():
        runtime = local_runtime(tmp_path)
        original = runtime.store.async_save
        attempts = 0

        async def flaky(**kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise OSError("busy")
            await original(**kwargs)

        runtime.store.async_save = flaky
        with pytest.raises(OSError):
            await runtime.persist()
        await asyncio.wait_for(runtime.stop(), 1)
        await runtime.hass.drain()
        assert attempts == 2 and len(runtime.store.writes) == 1
        assert not runtime._persistence_waiters

    asyncio.run(scenario())


def test_config_commit_and_state_writer_never_overlap_or_restore_old_configuration(tmp_path):
    async def scenario():
        runtime = local_runtime(tmp_path)
        original = runtime.store.async_save
        release, started = asyncio.Event(), asyncio.Event()
        calls, concurrent, maximum = 0, 0, 0

        async def delayed(**kwargs):
            nonlocal calls, concurrent, maximum
            calls += 1
            concurrent += 1
            maximum = max(maximum, concurrent)
            try:
                if calls == 1:
                    started.set()
                    await release.wait()
                await original(**kwargs)
            finally:
                concurrent -= 1

        runtime.store.async_save = delayed
        initial = asyncio.create_task(runtime.persist())
        await started.wait()
        candidate = runtime.config.to_dict()
        candidate["rooms"]["r"]["name"] = "Neuer Raumname"
        config = asyncio.create_task(runtime.update_config(candidate, runtime.config.revision))
        later = asyncio.create_task(runtime.persist())
        await spin_until(lambda: runtime._persistence_requested == 2)
        release.set()
        await asyncio.gather(initial, config, later)
        await runtime.hass.drain()
        assert maximum == 1
        assert runtime.config.rooms["r"].name == "Neuer Raumname"
        assert runtime.store.config.rooms["r"].name == "Neuer Raumname"
        assert runtime.store.config.revision == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("save", [False, True])
def test_shutdown_cancels_a_hung_writer_without_task_leaks(tmp_path, monkeypatch, save):
    monkeypatch.setattr(runtime_module, "_PERSISTENCE_SHUTDOWN_WAIT", 0.01)

    async def scenario():
        runtime = local_runtime(tmp_path)
        started, cancelled = asyncio.Event(), asyncio.Event()

        async def hung(**kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        runtime.store.async_save = hung
        caller = asyncio.create_task(runtime.persist())
        await started.wait()
        await asyncio.wait_for(runtime.stop(save=save), 1)
        with pytest.raises(asyncio.CancelledError):
            await caller
        assert cancelled.is_set() and not runtime._persistence_waiters
        await runtime.hass.drain()

    asyncio.run(scenario())
