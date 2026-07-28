"""Test solax_modbus setup process."""

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

from custom_components.solax_modbus import SolaXModbusHub
from custom_components.solax_modbus.const import DOMAIN


def test_domain_constant() -> None:
    """Test that the domain constant is correct."""
    assert DOMAIN == "solax_modbus"


def _initial_refresh_hub() -> SolaXModbusHub:
    hub = object.__new__(SolaXModbusHub)
    hub._initial_refresh_done = False
    hub._initial_refresh_task = None
    hub._platforms_forwarded = True
    hub._stopping = False
    hub.groups = {}

    def create_task(coro: Any) -> object:
        coro.close()
        return SimpleNamespace(done=lambda: False)

    hub._hass = SimpleNamespace(loop=SimpleNamespace(create_task=Mock(side_effect=create_task)))
    return hub


def test_initial_refresh_waits_for_registered_groups() -> None:
    """Initial refresh must not be consumed before entities register their groups."""
    hub = _initial_refresh_hub()

    hub._start_initial_refresh_if_needed()

    hub._hass.loop.create_task.assert_not_called()
    assert hub._initial_refresh_task is None

    hub.groups[10] = SimpleNamespace(device_groups={"inverter": object()})
    hub._start_initial_refresh_if_needed()

    hub._hass.loop.create_task.assert_called_once()
    assert hub._initial_refresh_task is not None


def test_initial_refresh_replaces_completed_task() -> None:
    """A task that returned before setup completed must not block a retry."""
    hub = _initial_refresh_hub()
    hub.groups[10] = SimpleNamespace(device_groups={"inverter": object()})
    hub._initial_refresh_task = SimpleNamespace(done=lambda: True)

    hub._start_initial_refresh_if_needed()

    hub._hass.loop.create_task.assert_called_once()


def test_initial_refresh_early_exit_releases_task() -> None:
    """An early exit must allow a later registration to schedule another refresh."""
    hub = _initial_refresh_hub()
    hub._probe_ready = asyncio.Event()
    hub._probe_ready.set()
    hub._initial_refresh_task = object()

    asyncio.run(hub._run_initial_refresh_when_ready())

    assert hub._initial_refresh_task is None


def test_initial_refresh_is_awaited() -> None:
    """Config entry setup must not finish before the startup refresh."""
    hub = object.__new__(SolaXModbusHub)
    refresh_finished = False

    async def run_test() -> None:
        nonlocal refresh_finished

        async def refresh() -> None:
            nonlocal refresh_finished
            await asyncio.sleep(0)
            refresh_finished = True

        hub._initial_refresh_task = asyncio.create_task(refresh())
        await hub._await_initial_refresh_if_started()

    asyncio.run(run_test())

    assert refresh_finished


def test_initial_refresh_computes_once_after_all_scan_groups() -> None:
    """Startup must publish computed values only after all scan groups were read."""
    hub = object.__new__(SolaXModbusHub)
    hub._name = "SolaX"
    hub._stopping = False
    hub._initial_refresh_done = False
    hub._initial_refresh_active = False
    hub._initial_refresh_task = object()
    hub.blocks_changed = False
    hub.cyclecount = 0
    hub.slowdown = 1
    hub.sleepnone = []
    hub.sleepzero = []
    hub.data = {}

    computed_sensor = SimpleNamespace(
        hass=object(),
        entity_id="sensor.solax_total",
        modbus_data_updated=Mock(),
    )
    hub.sensorEntities = {"total": computed_sensor}
    hub.computedSensors = {
        "total": SimpleNamespace(
            key="total",
            internal=False,
            value_function=lambda _value, _description, data: data.get("slow", 0) + data.get("fast", 0),
        )
    }

    async def run_test() -> None:
        hub._probe_ready = asyncio.Event()
        hub._probe_ready.set()

        async def read_group(group: Any) -> bool:
            hub.data.update(group.values)
            return True

        async def refresh_dashboard() -> None:
            return None

        hub.async_read_modbus_data = read_group
        hub._maybe_refresh_energy_dashboard_on_primary_update = refresh_dashboard
        hub.groups = {
            60: SimpleNamespace(
                device_groups={"slow": SimpleNamespace(sensors=[], values={"slow": 4})},
                poll_lock=asyncio.Lock(),
            ),
            5: SimpleNamespace(
                device_groups={"fast": SimpleNamespace(sensors=[], values={"fast": 6})},
                poll_lock=asyncio.Lock(),
            ),
        }

        await hub._run_initial_refresh_when_ready()

    asyncio.run(run_test())

    assert hub.data["total"] == 10
    computed_sensor.modbus_data_updated.assert_called_once_with()
    assert hub._initial_refresh_done is True
    assert hub._initial_refresh_task is None


def test_computed_sensors_refresh_after_all_device_groups() -> None:
    """Computed values must use the complete interval data and publish once."""
    hub = object.__new__(SolaXModbusHub)
    hub._name = "SolaX"
    hub.blocks_changed = False
    hub.cyclecount = 0
    hub.slowdown = 1
    hub.sleepnone = []
    hub.sleepzero = []
    hub.data = {}

    computed_sensor = SimpleNamespace(
        hass=object(),
        entity_id="sensor.solax_total",
        modbus_data_updated=Mock(),
    )
    hub.sensorEntities = {"total": computed_sensor}
    hub.computedSensors = {
        "total": SimpleNamespace(
            key="total",
            internal=False,
            value_function=lambda _value, _description, data: data.get("first", 0) + data.get("second", 0),
        )
    }

    async def read_group(group: Any) -> bool:
        hub.data.update(group.values)
        return True

    hub.async_read_modbus_data = read_group
    interval_group = SimpleNamespace(
        device_groups={
            "first": SimpleNamespace(sensors=[], values={"first": 4}),
            "second": SimpleNamespace(sensors=[], values={"second": 6}),
        }
    )

    result, updated_sensors = asyncio.run(hub._refresh_interval_group_once(interval_group))

    assert result is True
    assert updated_sensors == 0
    assert hub.data["total"] == 10
    computed_sensor.modbus_data_updated.assert_called_once_with()


def test_computed_sensors_follow_dependency_order() -> None:
    """A computed input must be refreshed before its dependent sensor."""
    hub = object.__new__(SolaXModbusHub)
    hub._name = "SolaX"
    hub.data = {"phase_1": 3, "phase_2": 5}
    hub.sensorEntities = {}
    hub.computedSensors = {
        "house_load": SimpleNamespace(
            key="house_load",
            internal=False,
            depends_on=["inverter_power"],
            value_function=lambda _value, _description, data: data.get("inverter_power", 0) + 2,
        ),
        "inverter_power": SimpleNamespace(
            key="inverter_power",
            internal=False,
            depends_on=["phase_1", "phase_2"],
            value_function=lambda _value, _description, data: data["phase_1"] + data["phase_2"],
        ),
    }

    hub._refresh_computed_sensor_states()

    assert hub.data["inverter_power"] == 8
    assert hub.data["house_load"] == 10


def test_computed_sensor_dependency_chains_are_loaded() -> None:
    """Raw inputs must stay polled through disabled computed intermediates."""
    hub = object.__new__(SolaXModbusHub)
    hub._hass = object()
    hub.entity_dependencies = {
        "inverter_power_l1": ["inverter_power"],
        "inverter_power": ["house_load"],
    }
    hub.selectEntities = {}
    hub.numberEntities = {}
    hub.switchEntities = {}
    hub.sensorEntities = {}
    hub.sensorDescriptions = {
        "inverter_power": SimpleNamespace(key="inverter_power"),
        "house_load": SimpleNamespace(key="house_load"),
    }

    def is_enabled(_hass: Any, _hub: Any, descriptor: Any) -> bool:
        return descriptor.key == "house_load"

    with patch("custom_components.solax_modbus.should_register_be_loaded", side_effect=is_enabled):
        assert hub._is_dependency_for_enabled_control("inverter_power_l1") is True


def test_computed_sensor_dependency_cycles_terminate() -> None:
    """Malformed dependency cycles must not recurse forever."""
    hub = object.__new__(SolaXModbusHub)
    hub._hass = object()
    hub.entity_dependencies = {
        "first": ["second"],
        "second": ["first"],
    }
    hub.selectEntities = {}
    hub.numberEntities = {}
    hub.switchEntities = {}
    hub.sensorEntities = {}
    hub.sensorDescriptions = {
        "first": SimpleNamespace(key="first"),
        "second": SimpleNamespace(key="second"),
    }

    with patch("custom_components.solax_modbus.should_register_be_loaded", return_value=False):
        assert hub._is_dependency_for_enabled_control("first") is False
