"""Test-only adapters. Load unchanged production bodies; substitute HA infrastructure.

No server connection, production storage, service call or configuration mutation.
The AST loader removes only HA imports (and the storage adapter import); all
integration business logic executes directly from the audited source files.
"""

import ast
import asyncio
import importlib
import sys
import types
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components" / "iqalarm"
package = types.ModuleType("safety_iqalarm")
package.__path__ = [str(SOURCE)]
sys.modules[package.__name__] = package
models = importlib.import_module("safety_iqalarm.models")
engine_module = importlib.import_module("safety_iqalarm.correlation_engine")
windows_module = importlib.import_module("safety_iqalarm.windows")


class HAError(Exception):
    """Infrastructure exception stand-in, no change to integration behavior."""


class MemoryStore:
    def __init__(self, hass):
        self.config = models.Configuration()
        self.state = {}
        self.outputs = {}
        self.writes = []

    async def async_save(self, config=None, state=None, outputs=None):
        self.config = config or self.config
        self.state = deepcopy(self.state if state is None else state)
        self.outputs = deepcopy(self.outputs if outputs is None else outputs)
        self.writes.append((self.config.to_dict(), self.state, self.outputs))


def load_body(filename):
    name = "safety_iqalarm." + filename.removesuffix(".py")
    if name in sys.modules:
        return sys.modules[name]
    module = types.ModuleType(name)
    module.__file__ = str(SOURCE / filename)
    module.__package__ = "safety_iqalarm"
    module.__dict__.update(
        HomeAssistant=object,
        HomeAssistantError=HAError,
        callback=lambda func: func,
        IQAlarmStore=MemoryStore,
        EVENT_HOMEASSISTANT_STOP="stop",
        EVENT_STATE_CHANGED="state_changed",
        async_dispatcher_send=lambda hass, signal: hass.published.append(signal),
        dt_util=NS(now=lambda: datetime.now(UTC), as_local=lambda dt: dt),
        er=NS(async_get=lambda hass: NS(async_get=lambda key: None)),
    )
    tree = ast.parse((SOURCE / filename).read_text(encoding="utf-8"))
    tree.body = [
        node
        for node in tree.body
        if not (
            isinstance(node, ast.ImportFrom)
            and (
                (node.module or "").startswith("homeassistant")
                or (node.level == 1 and node.module == "store")
            )
        )
    ]
    sys.modules[name] = module
    exec(compile(tree, module.__file__, "exec"), module.__dict__)
    return module


action_module = load_body("action_dispatcher.py")
runtime_module = load_body("runtime.py")


class StateTable:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, attributes=None):
        self.values[key] = NS(entity_id=key, state=value, attributes=attributes or {})


class ServiceRecorder:
    def __init__(self, states):
        self.states = states
        self.calls = []
        self.hooks = {}

    def has_service(self, domain, service):
        return True

    async def async_call(self, domain, service, data, blocking):
        self.calls.append((domain, service, deepcopy(data)))
        hook = self.hooks.get((domain, service))
        if hook:
            await hook(data)
        if service in ("turn_on", "turn_off"):
            self.states.set(data["entity_id"], "on" if service == "turn_on" else "off")


class LocalHA:
    def __init__(self, path):
        self.states = StateTable()
        self.services = ServiceRecorder(self.states)
        self.published = []
        self.events = []
        self.tasks = set()
        self.config = NS(
            path=lambda *parts: str(path.joinpath(*parts)), allowlist_external_dirs=set()
        )
        self.bus = NS(async_fire=lambda kind, data: self.events.append((kind, data)))

    def async_create_background_task(self, coroutine, name):
        task = asyncio.create_task(coroutine, name=name)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async_create_task = async_create_background_task

    async def drain(self):
        while self.tasks:
            await asyncio.gather(*list(self.tasks))

    async def async_add_executor_job(self, fn, *args):
        return fn(*args)


def base_config():
    return models.Configuration(
        rooms={"r": models.Room("r", "Test-Raum")},
        sensors={
            "binary_sensor.contact": models.SensorConfig(
                "binary_sensor.contact", "entry_contact", "r"
            ),
            "binary_sensor.contact2": models.SensorConfig(
                "binary_sensor.contact2", "entry_contact", "r"
            ),
            "binary_sensor.motion": models.SensorConfig(
                "binary_sensor.motion", "interior_motion", "r"
            ),
            "binary_sensor.motion2": models.SensorConfig(
                "binary_sensor.motion2", "interior_motion", "r"
            ),
            "binary_sensor.panic": models.SensorConfig("binary_sensor.panic", "panic", "r"),
        },
    )


def core(config=None):
    instance = engine_module.CorrelationEngine(config or base_config())
    for key in instance.sensors:
        instance.seed(key, False)
    return instance


def local_runtime(path, config=None):
    hass = LocalHA(path)
    instance = runtime_module.IQAlarmRuntime(hass, NS(data={}, entry_id="audit-only"))
    instance.engine = core(config)
    instance.store.config = instance.config
    for key in instance.config.sensors:
        hass.states.set(key, "off")
    instance._next_simulation = float("inf")
    instance._next_prune = float("inf")
    return instance


async def yield_events():
    for _ in range(5):
        await asyncio.sleep(0)
