# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Code Quality
```bash
# Lint and format code
ruff check custom_components/poolmath/
ruff format custom_components/poolmath/

# Run Home Assistant validation
ha-hassfest --requirements --action validate --integration-path custom_components/poolmath
```

### Testing and Development
There is currently no automated test suite. For manual testing:
```bash
# Copy to Home Assistant for testing
scp -r custom_components/poolmath homeassistant.local:/config/custom_components
ssh homeassistant.local "rm /config/*.log ; ha core restart"
```

## Architecture Overview

This is a Home Assistant custom integration for Pool Math (Trouble Free Pool) using a **hybrid coordinator pattern** that combines both legacy and modern HA patterns.

### Core Data Flow
1. **Configuration**: Users provide Pool Math share URL → extracted to `user_id`/`pool_id`
2. **Data Fetching**: `PoolMathUpdateCoordinator` polls Pool Math API every 8 minutes
3. **Sensor Management**: `PoolMathServiceSensor` acts as coordinator + creates individual `UpdatableSensor` entities
4. **State Updates**: Individual sensors display chemistry and equipment data in HA

### Key Components

**`sensor.py`** (470 lines) - Main implementation
- `PoolMathServiceSensor`: Legacy coordinator that manages child sensors and handles periodic updates
- `UpdatableSensor`: Individual sensor entities for each measurement (pH, FC, CC, etc.)
- Implements both RestoreSensor and CoordinatorEntity patterns
- Calculates Total Chlorine (TC = FC + CC) automatically

**`client.py`** - Pool Math API client using aiohttp (note: manifest incorrectly lists httpx)
- Parses Pool Math JSON responses using jsonpath
- Extracts user_id/pool_id from share URLs
- Handles API rate limiting and error responses

**`coordinator.py`** - Modern HA DataUpdateCoordinator (newer addition)

**`config_flow.py`** - Setup flow with options for reconfiguration

**`targets.py`** - Sensor definitions and chemistry target ranges
- Extensible target system (currently only TFP targets implemented)
- Defines sensor metadata (names, units, icons, device classes)

**`repairs.py`** - Handles migration from deprecated `share_id` to `user_id`/`pool_id` format

### Technical Debt Notes

1. **Hybrid Architecture**: Uses both legacy custom coordinator (`PoolMathServiceSensor`) and modern `DataUpdateCoordinator` - consider consolidating
2. **Translation Gaps**: Many strings hardcoded instead of using strings.json translations
3. **Target System**: Partially implemented - other target profiles (BioGuard, etc.) exist in `/targets/` but aren't fully integrated
4. **Dependency Mismatch**: manifest.json specifies `httpx` but code uses `aiohttp`

## Configuration and Data Models

**Configuration Migration**: Integration automatically migrates from old share_id format to new user_id/pool_id format using the repairs system.

**Supported Measurements**:
- Chemistry: pH, FC, CC, TC, TA, CH, CYA, Salt, Borates, CSI
- Equipment: Temperature, Pressure, Flow Rate, SWG Cell Percentage

## Pool Math API Integration

- **Rate Limiting**: Updates every 8 minutes (Pool Math caches for 10 min, rate limits to 1/min)
- **Share URL Format**: `https://www.troublefreepool.com/mypool/{user_id}/{pool_id}`
- **Error Handling**: Graceful degradation when Pool Math service is unavailable
- **Authentication**: Uses public share URLs (no authentication required)

## Home Assistant Integration Details

- **Integration Type**: `hub` with `cloud_polling` IoT class
- **Minimum HA Version**: 2025.3.0 (specified in hacs.json)
- **HACS**: Available as default repository
- **Dependencies**: jsonpath, httpx (though aiohttp is actually used)