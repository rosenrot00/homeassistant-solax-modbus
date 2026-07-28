"""Tests for control state publication around Modbus writes."""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.solax_modbus.const import BaseModbusSwitchEntityDescription
from custom_components.solax_modbus.switch import SolaXModbusSwitch


@pytest.mark.asyncio
async def test_accepted_switch_write_publishes_logical_readback() -> None:
    """Publish the expected state immediately after the device accepts a write."""

    def _inverted_payload(_bit: int | None, is_on: bool | None, _sensor_key: str | None, _data: dict[str, Any]) -> int:
        return 0 if is_on else 1

    description = BaseModbusSwitchEntityDescription(
        key="modbus_switch",
        name="modbus_switch",
        register=0x99,
        sensor_key="readback",
        value_function=_inverted_payload,
    )
    hub = SimpleNamespace(
        async_write_registers_single=AsyncMock(),
        data={"readback": 0},
        name="SolaX",
    )

    def record_control_write(key: str, value: Any) -> None:
        hub.data[key] = value

    hub.record_control_write = Mock(side_effect=record_control_write)
    switch = SolaXModbusSwitch("SolaX", hub, 1, cast(Any, {}), description)

    with patch.object(switch, "async_write_ha_state") as write_state:
        await switch.async_turn_on()

    hub.async_write_registers_single.assert_awaited_once_with(
        unit=1,
        address=0x99,
        payload=0,
        register_data_type=None,
    )
    hub.record_control_write.assert_called_once_with("readback", 1)
    assert switch.is_on is True
    write_state.assert_called_once_with()


@pytest.mark.asyncio
async def test_bitfield_switch_preserves_unrelated_readback_bits() -> None:
    """Optimistic state updates must only change the switch's configured bit."""

    def _mutate_bit(bit: int | None, is_on: bool | None, sensor_key: str | None, data: dict[str, Any]) -> int:
        assert bit is not None and sensor_key is not None
        value = int(data[sensor_key])
        return (value & ~(1 << bit)) | (int(bool(is_on)) << bit)

    description = BaseModbusSwitchEntityDescription(
        key="bitfield_switch",
        name="bitfield_switch",
        register=0x9E,
        register_bit=1,
        sensor_key="readback",
        value_function=_mutate_bit,
    )
    hub = SimpleNamespace(
        async_write_registers_single=AsyncMock(),
        data={"readback": 0b1010},
        name="SolaX",
    )

    def record_control_write(key: str, value: Any) -> None:
        hub.data[key] = value

    hub.record_control_write = Mock(side_effect=record_control_write)
    switch = SolaXModbusSwitch("SolaX", hub, 1, cast(Any, {}), description)

    with patch.object(switch, "async_write_ha_state"):
        await switch.async_turn_off()

    hub.async_write_registers_single.assert_awaited_once_with(
        unit=1,
        address=0x9E,
        payload=0b1000,
        register_data_type=None,
    )
    hub.record_control_write.assert_called_once_with("readback", 0b1000)
    assert switch.is_on is False


def test_switch_readback_callback_and_polling_contract() -> None:
    description = BaseModbusSwitchEntityDescription(
        key="modbus_switch",
        name="modbus_switch",
        register=1,
        sensor_key="readback",
    )
    hub = SimpleNamespace(data={"readback": 1}, name="SolaX")
    switch = SolaXModbusSwitch("SolaX", hub, 1, cast(Any, {}), description)

    with patch.object(switch, "async_write_ha_state") as write_state:
        switch.modbus_data_updated()

    assert switch.should_poll is False
    write_state.assert_called_once_with()
