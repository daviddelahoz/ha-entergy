<p align="center">
  <img src="assets/entergy-wordmark.svg" alt="Entergy" width="560">
</p>

# Entergy

Home Assistant custom integration for Entergy electric usage data.

This integration signs in with your Entergy account, lets you select an account during setup, and creates sensors for recent usage, cost, and Energy Dashboard-friendly cumulative import/export totals.

> This project is unofficial and is not affiliated with, endorsed by, or supported by Entergy.

<p align="center">
  <a href="https://www.buymeacoffee.com/daviddelahoz" target="_blank">
    <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me a Coffee" height="60" width="217">
  </a>
</p>

## Features

- Config flow setup from the Home Assistant UI
- Account selection during setup
- Cloud polling for Entergy usage data
- Latest hour, latest day, last 7 days, and month-to-date usage sensors
- Cost sensors when cost data is returned by Entergy
- Cumulative import and export energy sensors for the Home Assistant Energy Dashboard
- Diagnostics support with sensitive values redacted

## Sensors

Energy Dashboard-friendly sensors:

- Imported Energy Total
- Exported Energy Total

Usage and cost sensors:

- Latest Hour Net Usage
- Latest Hour Import
- Latest Hour Export
- Latest Hour Cost
- Latest Day Net Usage
- Latest Day Import
- Latest Day Export
- Latest Day Cost
- Last 7 Days Net Usage
- Last 7 Days Cost
- Month-to-Date Net Usage
- Month-to-Date Cost
- Tracked Hourly Intervals
- Latest Hour Timestamp

## Installation

### HACS custom repository

1. Open HACS.
2. Go to Custom repositories.
3. Add `https://github.com/daviddelahoz/ha-entergy`.
4. Select category `Integration`.
5. Install `Entergy`.
6. Restart Home Assistant.
7. Go to Settings, Devices & services, Add integration.
8. Search for `Entergy`.

### Manual installation

Copy this integration folder to:

```text
/config/custom_components/entergy_mobile
```

Then restart Home Assistant and add the integration from Settings, Devices & services.

For a standard GitHub repository layout, the files should be arranged as:

```text
ha-entergy/
  README.md
  assets/
    entergy-icon.svg
    entergy-wordmark.svg
  custom_components/
    entergy_mobile/
      __init__.py
      api.py
      config_flow.py
      const.py
      coordinator.py
      diagnostics.py
      entity.py
      manifest.json
      sensor.py
      strings.json
      translations/
        en.json
```

## Configuration

1. In Home Assistant, go to Settings, Devices & services.
2. Select Add integration.
3. Search for `Entergy`.
4. Enter your Entergy credentials.
5. Choose the Entergy account to monitor.

The integration stores the access token only in memory. Home Assistant stores the credentials in the config entry so the integration can log in again after restart.

## Energy Dashboard

Use these sensors in the Home Assistant Energy Dashboard:

- `Imported Energy Total` for grid consumption
- `Exported Energy Total` for returned energy

The Entergy service returns interval usage data, not a lifetime meter reading. To make Energy Dashboard totals work, this integration stores seen hourly intervals in Home Assistant storage and only adds new import/export values to cumulative totals.

Important behavior:

- Totals start from the first successful integration run.
- Historical data before setup is not backfilled.
- Deleting the integration storage resets the cumulative totals.
- If Entergy later revises an interval downward, the cumulative total is not reduced.

## Options

The update interval can be changed from the integration options.

Default:

```text
3600 seconds
```

Allowed range:

```text
300 to 86400 seconds
```

## Debug Logging

To troubleshoot setup or polling, enable debug logs:

```yaml
logger:
  default: info
  logs:
    custom_components.entergy_mobile: debug
```

Restart Home Assistant, reproduce the issue, then check Settings, System, Logs.

Sensitive values such as username, password, authorization headers, client ID, and access tokens should not be logged.

## Known Limitations

- Additional login challenges, such as MFA or unsupported next actions, may not work yet.
- The integration depends on Entergy service behavior, which can change without notice.
- Energy Dashboard totals are derived from interval data and local persistent storage.

## Development

Validate Python syntax locally:

```bash
python -m compileall custom_components/entergy_mobile
```

For this workspace, if you are already inside the integration folder:

```bash
python -m compileall .
```
