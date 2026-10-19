"""Profile ownership is enforced by real dispatcher bodies, including dry runs."""

import asyncio

import pytest
from safety_support import local_runtime, models


def test_level_three_test_ceiling_blocks_high_actions_and_manual_tests(tmp_path):
    async def scenario():
        config = models.Configuration(
            automatic_detection=models.AutomaticDetection(),
            rooms={"r": models.Room("r", "Raum")},
            sensors={
                "binary_sensor.motion": models.SensorConfig(
                    "binary_sensor.motion", "interior_motion", "r"
                )
            },
        )
        config.actions = {
            stage: models.Action(
                stage, stage, "notify", "notify.phone", message=stage, profile_ids=["armed_away"]
            )
            for stage in ("3", "4", "5")
        }
        runtime = local_runtime(tmp_path, config)
        runtime.engine.set_profile("armed_away", 100)
        for stage in ("4", "5"):
            for dry_run in (True, False):
                with pytest.raises(ValueError, match="Testbetrieb deaktiviert"):
                    await runtime.test_level(stage, dry_run=dry_run, profile_id="armed_away")
                event = models.EventLog(
                    100,
                    "test",
                    int(stage),
                    "active",
                    "Alte vorgemerkte Aktion",
                    stage_id=stage,
                    profile_id="armed_away",
                    confirmed=stage == "5",
                    reactions_enabled=True,
                )
                assert await runtime.dispatcher.dispatch(event, 0, dry_run=dry_run) == []
        assert not runtime.hass.services.calls
        plan = await runtime.test_level("3", dry_run=False, profile_id="armed_away")
        assert [action["id"] for action in plan] == ["3"]
        assert [call[2]["message"] for call in runtime.hass.services.calls] == ["3"]

    asyncio.run(scenario())


def test_real_and_dry_profile_plans_never_mix_modes(tmp_path):
    async def scenario():
        runtime = local_runtime(tmp_path)
        runtime.config.stages = models.default_stages()
        runtime.config.secure_stage_id = "1"
        runtime.config.rules = models.default_rules()
        runtime.config.actions = {
            "night": models.Action(
                "night", "3", "notify", "notify.phone", message="Nacht", profile_ids=["armed_night"]
            ),
            "away": models.Action(
                "away",
                "3",
                "notify",
                "notify.phone",
                message="Abwesend",
                profile_ids=["armed_away"],
            ),
        }
        runtime.config.validate()
        plan = await runtime.test_level("3", profile_id="armed_away")
        assert [a["id"] for a in plan] == ["away"]
        assert not runtime.hass.services.calls
        await runtime.test_level("3", dry_run=False, profile_id="armed_night")
        assert [c[2]["message"] for c in runtime.hass.services.calls] == ["Nacht"]

    asyncio.run(scenario())


def test_entry_and_full_confirmation_actions_are_separate_and_profile_scoped(tmp_path):
    async def scenario():
        runtime = local_runtime(tmp_path)
        runtime.config.stages = models.default_stages()
        runtime.config.secure_stage_id = "1"
        runtime.config.rules = models.default_rules()
        runtime.config.actions = {
            key: models.Action(
                key,
                "2",
                "notify",
                "notify.phone",
                message=key,
                trigger=trigger,
                profile_ids=[profile],
            )
            for key, trigger, profile in (
                ("entry", "level_entered", "armed_night"),
                ("full", "rule_confirmed", "armed_night"),
                ("vacation", "rule_confirmed", "armed_vacation"),
            )
        }
        runtime.engine.profile_id = "armed_night"
        for kind, profile, expected in (
            ("level_changed", "armed_night", "entry"),
            ("rule_confirmation", "armed_night", "full"),
            ("rule_confirmation", "armed_vacation", "vacation"),
        ):
            event = models.EventLog(
                100,
                kind,
                2,
                "active",
                "Test",
                stage_id="2",
                profile_id=profile,
                reactions_enabled=True,
            )
            plan = await runtime.dispatcher.dispatch(event, runtime.generation)
            assert [item["id"] for item in plan] == [expected]
        assert [call[2]["message"] for call in runtime.hass.services.calls] == [
            "entry",
            "full",
            "vacation",
        ]
        # Observation can update grades, but never sends a completion notification.
        event.reactions_enabled = False
        assert await runtime.dispatcher.dispatch(event, runtime.generation) == []
        assert len(runtime.hass.services.calls) == 3

    asyncio.run(scenario())


def test_rule_completion_is_queued_once_without_replaying_entry_actions(tmp_path):
    async def scenario():
        runtime = local_runtime(tmp_path)
        runtime.config.stages = models.default_stages()
        runtime.config.secure_stage_id = "1"
        runtime.config.rules = models.default_rules()
        runtime.engine.profile_id = "armed_night"
        runtime.engine.drain()
        event = models.EventLog(
            100,
            "rule_confirmation",
            2,
            "active",
            "Test",
            stage_id="2",
            profile_id="armed_night",
            reactions_enabled=True,
        )
        runtime.engine._outbox.append(event)
        await runtime.flush()
        queued, generation = runtime.queue.get_nowait()
        assert queued is event and generation == runtime.generation
        assert runtime.queue.empty()
        await runtime.flush()
        assert runtime.queue.empty()

    asyncio.run(scenario())
