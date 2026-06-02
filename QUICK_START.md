# Battery Remaining Time - Quick Start Guide

## Installation

### Option 1: HACS (Recommended)

1. Go to **Settings** → **Devices & Services** → **Custom Repositories**
2. Add the repository URL:
   ```
   https://github.com/sundeepgoel72/HA-battery-remainingtime-integration
   ```
3. Category: Select **Integration**
4. Click **Create**
5. Go to **Settings** → **Devices & Services** → **Integrations**
6. Click **Create Integration** (or search for "Battery Remaining Time")
7. Select **Battery Remaining Time**
8. Follow the configuration wizard

### Option 2: Manual Installation

1. Copy the `custom_components/battery_remaining_time` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Go to **Settings** → **Devices & Services** → **Create Integration**
4. Search for "Battery Remaining Time"

---

## Configuration

### Step 1: Basic Settings

When creating the integration, you'll be asked for:

- **Name:** Display name for this battery (e.g., "Solar Inverter Battery")
- **Algorithm:** Prediction model (recommended: **Ensemble** for best accuracy)
- **Battery Type:** Select your battery chemistry:
  - Flooded Lead Acid (standard automotive)
  - Tubular Lead Acid (high performance)
  - AGM (maintenance-free, fast charging)
  - Gel (sealed, slow discharge)
  - Lead Carbon (extended life)
  - Custom (if unsure)
- **Battery Capacity:** Battery capacity in Amp-hours (Ah) - found on battery label
- **Nominal Voltage:** System voltage (12V, 24V, 36V, 48V, 60V, or 72V)
- **Depletion Voltage:** Minimum safe voltage (auto-calculated, can override)

### Step 2: Sensor Configuration

- **Battery Voltage Sensor:** (Required) Entity providing voltage readings
  - Example: `sensor.battery_voltage`
  - Must be in Volts
- **Battery Current Sensor:** (Optional) Entity providing current readings
  - Example: `sensor.battery_current`
  - Positive for charging, negative for discharging
- **History Window:** (Default: 60 minutes) Data lookback for trend analysis
- **Update Interval:** (Default: 60 seconds) How often to recalculate predictions

### Step 3: Advanced Settings (Optional)

Access via **Settings** → **Devices & Services** → **Battery Remaining Time** → **Options**

- **Charge Power Sensor:** Alternative to current sensor
  - Example: `sensor.charge_power` (in Watts)
- **Discharge Power Sensor:** Alternative to current sensor
  - Example: `sensor.load_power` (in Watts)
- **Temperature Sensor:** For temperature-compensated algorithms
  - Example: `sensor.battery_temp` (in °C)

---

## Available Sensors

After setup, the following entities are created:

### Main Sensors

| Sensor | Example | Description |
|--------|---------|-------------|
| `estimated_soc` | `sensor.battery_estimated_soc` | Battery charge level (0-100%) |
| `time_to_empty` | `sensor.battery_time_to_empty` | Hours until fully discharged |
| `time_to_full` | `sensor.battery_time_to_full` | Hours until fully charged |
| `net_power` | `sensor.battery_net_power` | Current charging/discharging power (W) |
| `confidence` | `sensor.battery_confidence` | Prediction confidence (low/medium/high) |

### Diagnostic Sensors (Optional)

Enable in **Settings** → **Devices & Services** → **Entities** to see:

- **Prediction Health:** Overall prediction quality status
- **Calibration Status:** Learning progress (0-100%)
- **Algorithm Spread:** Model divergence indicator
- **Battery Health:** Estimated battery health %
- **Learned Capacity:** Actual measured capacity vs. configured
- **Learned Peukert Exponent:** Adaptive runtime correction factor
- **Per-Model SOC:** Individual algorithm predictions for debugging

---

## Example Dashboard Configuration

Add a card to your Home Assistant dashboard:

```yaml
type: entities
title: Battery Status
entities:
  - entity: sensor.battery_estimated_soc
    icon: mdi:battery
  - entity: sensor.battery_time_to_empty
    icon: mdi:clock-outline
  - entity: sensor.battery_time_to_full
    icon: mdi:lightning-bolt
  - entity: sensor.battery_confidence
  - entity: sensor.battery_net_power
    icon: mdi:power-plug
  - entity: sensor.battery_health
    icon: mdi:heart-pulse
```

Or using a gauge card:

```yaml
type: gauge
entity: sensor.battery_estimated_soc
min: 0
max: 100
unit: '%'
needle: true
segments:
  - from: 0
    color: '#ff0000'
  - from: 20
    color: '#ffaa00'
  - from: 60
    color: '#00ff00'
  - from: 90
    color: '#0000ff'
```

---

## Troubleshooting

### "Battery source sensors are unavailable"

**Problem:** Integration shows a warning that sensors cannot be found

**Solutions:**
1. Verify sensor entity IDs are correct (check **Developer Tools** → **States**)
2. Ensure sensors provide numeric values (not "unknown" or "unavailable")
3. Wait for sensor data to populate (some integrations have delays)
4. Check sensor availability in **Developer Tools** → **Events**

### Confidence stays "low"

**Problem:** Confidence metric is not improving

**Solutions:**
1. Run the battery through at least one charge/discharge cycle
2. Allow 24+ hours for historical data accumulation
3. Ensure history window (default 60 min) captures full charge/discharge events
4. Check **calibration_status** sensor for learning progress
5. Verify battery type selection matches actual battery

### SOC jumps unexpectedly

**Problem:** Battery percentage fluctuates wildly

**Solutions:**
1. Check if voltage sensor is noisy (spikes/drops)
2. Add a smoothing filter to the voltage sensor
3. Increase history window to 120-240 minutes
4. Verify current/power sensors are calibrated
5. Check for rapid SOC changes in **algorithm_spread** sensor

### Configuration Errors

**"No matching device found for entity"**
- Ensure the entity exists and is available
- Use **Developer Tools** → **States** to find correct entity ID

**"Invalid value"**
- Battery capacity must be positive number
- Voltage must match your system (12V, 24V, etc.)
- Depletion voltage must be below nominal voltage

---

## Tips for Best Results

1. **Initial Setup:** Leave default algorithm (Ensemble) for first month
2. **History Window:** Start with 60 minutes; increase if discharge cycles are longer
3. **Sensor Quality:** Use direct inverter/BMS sensors rather than derived calculations
4. **Temperature:** Add temperature sensor if available for better accuracy in varying climates
5. **Charging:** Ensure charger and discharge profiles are consistent
6. **Monitoring:** Watch **prediction_health** and **calibration_status** sensors
7. **Patience:** Calibration improves after 5-10 complete charge/discharge cycles

---

## Next Steps

- View **Diagnostics** to inspect per-model predictions
- Create automations based on **time_to_empty** thresholds
- Compare with other battery monitoring systems
- Report accuracy issues on GitHub

For detailed technical documentation, see the main README.md and docs/ folder.
