"""Regression tests for SolaX serial-prefix inverter detection."""

from typing import Any

import pytest

import custom_components.solax_modbus.plugin_solax as solax_module
from custom_components.solax_modbus.plugin_solax import (
    GEN,
    GEN2,
    GEN3,
    GEN4,
    GEN5,
    GEN6,
    HYBRID,
    MIC,
    MPPT3,
    MPPT4,
    SOLAX_SERIAL_PREFIX_RULES,
    X1,
    X3,
    identify_solax_inverter,
)
from custom_components.solax_modbus.plugin_solax import (
    plugin_instance as solax_plugin,
)


@pytest.mark.parametrize(
    ("serial_number", "expected_type", "expected_model"),
    [
        ("L3012345678901", HYBRID | GEN2 | X1, "X1-Hybrid-3.0kW SK-TL"),
        ("U3712345678901", HYBRID | GEN2 | X1, "X1-Hybrid-3.7kW SK-SU"),
        ("H1E37123456789", HYBRID | GEN3 | X1, "X1-Hybrid-3.7kW"),
        ("H3ET1012345678", HYBRID | GEN3 | X3, "X3-Hybrid-10kW"),
        ("63150123456789", HYBRID | GEN4 | X1, "X1-TIGO-TSI-5.0kW"),
        ("H34T1012345678", HYBRID | GEN4 | X3, "X3-Hybrid-10kW"),
        # Keep the existing X1 flag even though the model label says X3.
        ("H3VC8312345678", HYBRID | GEN4 | X1, "X3-Hybrid-8.3kW"),
        ("10M07123456789", HYBRID | GEN6 | X1 | MPPT3, "X1-VAST-7kW"),
        ("10M08123456789", HYBRID | GEN6 | X1 | MPPT4, "X1-VAST-8kW"),
        ("10K07123456789", HYBRID | GEN6 | X3, "X3-G4PRO-7kW"),
        ("10K08123456789", HYBRID | GEN6 | X3 | MPPT3, "X3-G4PRO-8kW"),
        ("MPT24123456789", MIC | GEN2 | X3, "X3-MIC PRO-24kW"),
        ("MPT25123456789", MIC | GEN2 | X3 | MPPT3, "X3-MIC PRO-25kW"),
        # The longer Ultra prefix must win over H3BC15.
        ("H3BC15L1234567", HYBRID | GEN5 | X3 | MPPT3, "X3-Ultra-15kW"),
        ("H3BC1512345678", HYBRID | GEN5 | X3, "X3-Ultra-15kW"),
        # Preserve existing model labels during this behavior-neutral refactor.
        ("H3BD2512345678", HYBRID | GEN5 | X3 | MPPT3, "X3-Ultra-20kW"),
        ("MC802T12345678", MIC | GEN | X3, None),
    ],
)
def test_identify_solax_inverter(
    serial_number: str,
    expected_type: int,
    expected_model: str | None,
) -> None:
    assert identify_solax_inverter(serial_number) == (expected_type, expected_model)


def test_serial_prefix_rules_cover_the_existing_prefix_set_once() -> None:
    prefixes = [prefix for rule in SOLAX_SERIAL_PREFIX_RULES for prefix in rule.prefixes]

    assert len(prefixes) == 122
    assert len(prefixes) == len(set(prefixes))
    assert all(identify_solax_inverter(f"{prefix}123456789") is not None for prefix in prefixes)


def test_unknown_serial_is_not_identified() -> None:
    assert identify_solax_inverter("NOT-A-SOLAX-SERIAL") is None


class DetectionHub:
    """Minimal hub used to verify the existing serial-register fallback flow."""

    def __init__(self) -> None:
        self.name = "SolaX"
        self.seriesnumber: str | None = None
        self.inverter_model: str | None = None
        self._has_local_inverter_model = False


CONFIG: dict[str, Any] = {
    "read_eps": False,
    "read_dcb": False,
    "read_pm": False,
}


@pytest.mark.asyncio
async def test_unknown_nonempty_serial_still_stops_register_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """SolaX must not adopt Growatt's search-after-unknown behavior."""
    hub = DetectionHub()
    responses = {0x0: "UNKNOWN123456", 0x300: "L3012345678901"}
    read_addresses: list[int] = []

    async def fake_read_serialnr(target_hub: Any, address: int) -> str | None:
        read_addresses.append(address)
        serial_number = responses.get(address)
        if serial_number:
            target_hub.seriesnumber = serial_number
        return serial_number

    monkeypatch.setattr(solax_module, "async_read_serialnr", fake_read_serialnr)

    inverter_type = await solax_plugin.async_determineInverterType(hub, CONFIG)

    assert inverter_type == 0
    assert read_addresses == [0x0]


@pytest.mark.asyncio
async def test_empty_serial_uses_existing_register_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    hub = DetectionHub()
    responses = {0x0: None, 0x300: "L3012345678901"}
    read_addresses: list[int] = []

    async def fake_read_serialnr(target_hub: Any, address: int) -> str | None:
        read_addresses.append(address)
        serial_number = responses.get(address)
        if serial_number:
            target_hub.seriesnumber = serial_number
        return serial_number

    monkeypatch.setattr(solax_module, "async_read_serialnr", fake_read_serialnr)

    inverter_type = await solax_plugin.async_determineInverterType(hub, CONFIG)

    assert inverter_type == HYBRID | GEN2 | X1
    assert hub.inverter_model == "X1-Hybrid-3.0kW SK-TL"
    assert read_addresses == [0x0, 0x300]
