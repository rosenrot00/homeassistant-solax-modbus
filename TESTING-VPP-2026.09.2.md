# SolaX direct VPP test build for 2026.09.2

This branch contains the complete **2026.09.2** integration plus the direct VPP
changes from [PR #2315](https://github.com/wills106/homeassistant-solax-modbus/pull/2315).
No other unreleased fixes or dependency updates are required.

Base: release `2026.09.2`, commit `5e55af7753765aad6981f2eef117d8b8adafec48`.
VPP fix: commit `e950f501ecde6d3d75316fee4fc7f202d87a1bdd`.

## Install over an existing 2026.09.2 installation

1. Make a Home Assistant backup, or keep a copy of your existing
   `/config/custom_components/solax_modbus` folder outside `custom_components`.
2. [Download this branch as a ZIP](https://github.com/rosenrot00/homeassistant-solax-modbus/archive/refs/heads/test/solax-vpp-2026.09.2.zip)
   and extract it.
3. Stop Home Assistant before replacing the files. From the extracted ZIP, copy
   the **contents** of `custom_components/solax_modbus/` into the existing
   `/config/custom_components/solax_modbus/` folder, overwriting matching files.
   Do not create a second nested `solax_modbus` folder.
4. Start Home Assistant again. A full restart is required, not just an
   integration reload.

Only copy that integration folder. Do not copy the repository root, its tests,
or its documentation into your Home Assistant configuration. Do not replace
`configuration.yaml`, `.storage`, or your existing integration settings.

There is no need to reinstall or reconfigure the integration in HACS. The
manifest version remains `2026.09.2`; that version display alone cannot identify
this test build. A HACS redownload/update will overwrite these test files.

For reference, the files changed from the original release are exactly:

- `custom_components/solax_modbus/__init__.py`
- `custom_components/solax_modbus/const.py`
- `custom_components/solax_modbus/number.py`
- `custom_components/solax_modbus/plugin_solax.py`
- `custom_components/solax_modbus/select.py`

## Test SOC target control

1. With direct VPP disabled, enter your intended values again in
   **Remotecontrol Target SOC (mode 3; direct)**,
   **Remotecontrol Charge/Discharge Power (mode 2/3; direct)**, and
   **Remotecontrol TimeOut (mode 1-7; direct)**. Use your own intended settings;
   this test build does not choose a battery target for you.
2. Unlock the inverter as required, then select **Enable SOC Target Control Mode**
   in **Modbus Power Control (direct)**.
3. Test switching back to **Disabled**, and report the result of both operations
   and any exact error messages.

The message `Set 'Remotecontrol Target SOC (mode 3; direct)' before enabling
direct VPP mode 3` means the integration has not yet been given a target SOC.
It is a local validation error before any VPP command is sent, not a Modbus
rejection. Earlier versions did not persist these direct parameters, so their
previously configured values may need to be entered again after installing this
test build.

During an active mode, relevant parameter changes still apply immediately.
If a mode has ended, changing a parameter does not automatically reactivate it.
See [direct VPP behavior and upgrade notes](docs/solax-direct-vpp.md) for details.

## Revert

Redownload the desired released version in HACS and fully restart Home Assistant,
or stop Home Assistant, restore your saved integration folder, and start it again.
Please state whether a reported result came from this test branch or a HACS release.
