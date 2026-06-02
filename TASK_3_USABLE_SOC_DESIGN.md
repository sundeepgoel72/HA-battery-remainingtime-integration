# Task 3: Usable SOC / Depletion Voltage Completion

**Objective:** Add depletion voltage feature with new sensors, diagnostics, and event states.

**Status:** Implementation Planning & Design  
**Target:** Complete by end of this session

---

## Overview

Task 3 implements operational battery State of Charge (usable SOC) for inverter users who need to stop discharge before the battery's chemical minimum. This prevents over-discharging lead-acid batteries below safe operating thresholds.

### Key Concepts

**Estimated SOC** (existing)
- 0-100% battery capacity from fully depleted to fully charged
- Includes inaccessible chemistry reserve

**Usable SOC** (new)
- 0-100% of practically accessible capacity between depletion voltage and full charge
- Accounts for inverter protection thresholds
- Stops discharge before `depletion_voltage` is reached
- Critical for inverter systems with low-voltage cutoff

**Depletion Voltage**
- Configured minimum voltage (e.g., 10.5V for 12V system = 87.5% capacity)
- User-specified or auto-calculated from nominal voltage
- Below this, battery chemistry is inaccessible/unsafe

---

## Requirements

### New Sensors

#### 1. sensor.{battery_name}_usable_soc
```yaml
Entity ID: sensor.{battery_name}_usable_soc
Type: Percentage (0-100%)
Unit: %
Device Class: battery
State Class: measurement
Enabled by Default: true
```

**Calculation:**
```
if voltage <= depletion_voltage:
    usable_soc = 0%
elif voltage >= full_voltage:
    usable_soc = 100%
else:
    voltage_range = full_voltage - depletion_voltage
    voltage_usable = voltage - depletion_voltage
    usable_soc = clamp((voltage_usable / voltage_range) * 100, 0, 100)
```

**Attributes:**
- `estimated_soc` - Full battery SOC for reference
- `depletion_voltage` - Configured cutoff
- `full_voltage` - Configured or learned full voltage
- `current_voltage` - Current battery voltage
- `mode` - Operating mode (charging/discharging/idle)

#### 2. sensor.{battery_name}_time_to_depletion
```yaml
Entity ID: sensor.{battery_name}_time_to_depletion
Type: Duration
Unit: h (hours)
Device Class: duration
State Class: measurement
Enabled by Default: true
```

**Description:** Runtime remaining until practical depletion voltage is reached (like TTE but from usable SOC perspective).

**Calculation:**
```
if usable_soc is None or mode != "discharging":
    time_to_depletion = None
else:
    usable_wh = capacity_wh * usable_soc / 100
    discharge_w = abs(net_power)
    time_to_depletion_h = usable_wh / discharge_w
```

**Attributes:**
- `usable_soc` - Current usable state of charge
- `discharge_power` - Current discharge rate in watts
- `depletion_voltage` - Voltage target
- `time_to_empty` - Chemical SOC equivalent (for reference)

### New Diagnostic Sensors

#### 3. sensor.{battery_name}_configured_depletion_voltage
```yaml
Entity ID: sensor.{battery_name}_configured_depletion_voltage
Type: Voltage
Unit: V
Device Class: voltage
State Class: measurement
Enabled by Default: false
Category: DIAGNOSTIC
```

**Value:** Static configured depletion voltage (from config)

#### 4. sensor.{battery_name}_learned_depletion_voltage
```yaml
Entity ID: sensor.{battery_name}_learned_depletion_voltage
Type: Voltage
Unit: V
Device Class: voltage
State Class: measurement
Enabled by Default: false
Category: DIAGNOSTIC
```

**Value:** Learned depletion voltage from observed behavior

**When used:**
- If confidence > "medium", prefer learned value
- Fall back to configured if confidence is low
- Share confidence metric

**Attributes:**
- `confidence` - Trust level in learned value (low/medium/high)
- `observation_count` - Number of observations
- `configured_voltage` - Original configured value
- `variance` - Observed variance in measurements

### New Event State

#### 5. depletion_imminent
```yaml
State: "depletion_imminent"
Evidence: [
    "usable_soc_below_5",
    "voltage_near_depletion",
    "discharge_continuing"
]
Calibration Anchor: true
```

**When triggered:**
- Usable SOC < 5% AND actively discharging
- Battery approaching inverter cutoff threshold
- Useful for automation alerts and learning events

---

## Implementation Plan

### Phase 1: Add to Predictor (predictor.py)

**Changes needed:**
1. Add `usable_soc_percent` field to `BatteryPrediction` dataclass
2. Add `time_to_depletion_h` field to `BatteryPrediction` dataclass
3. Add `depletion_voltage` parameter to `BatteryInputs` dataclass
4. Implement `practical_usable_soc()` function
5. Implement `time_to_depletion()` function
6. Update `prediction_to_telemetry()` to include new fields

**Functions to add:**

```python
def practical_usable_soc(
    inputs: BatteryInputs,
    soc: float | None
) -> float | None:
    """Return usable SOC above depletion voltage cutoff."""
    if soc is None or inputs.depletion_voltage is None:
        return None
    if inputs.depletion_voltage <= 0 or inputs.nominal_voltage <= 0:
        return None
    if inputs.voltage is None:
        return None
    if inputs.voltage <= inputs.depletion_voltage:
        return 0.0
    
    full_voltage = max(inputs.nominal_voltage * 1.067, inputs.depletion_voltage + 0.1)
    if inputs.voltage >= full_voltage:
        return min(soc, 100.0)
    
    voltage_range = full_voltage - inputs.depletion_voltage
    voltage_usable = inputs.voltage - inputs.depletion_voltage
    voltage_usable_soc = (voltage_usable / voltage_range) * 100.0
    
    return clamp(min(soc, voltage_usable_soc), 0.0, 100.0)


def time_to_depletion(
    inputs: BatteryInputs,
    usable_soc: float | None,
    net_power: float | None
) -> float | None:
    """Return runtime until depletion voltage is reached."""
    if (
        usable_soc is None
        or net_power is None
        or net_power >= -0.1
        or inputs.capacity_ah <= 0
        or inputs.nominal_voltage <= 0
    ):
        return None
    
    capacity_wh = inputs.capacity_ah * inputs.nominal_voltage
    usable_wh = capacity_wh * clamp(usable_soc, 0, 100) / 100.0
    discharge_w = abs(net_power)
    
    if discharge_w < 0.1:
        return None
    
    return usable_wh / discharge_w
```

### Phase 2: Add Event Detection (events.py)

**Changes needed:**
1. Add `STATE_DEPLETION_IMMINENT = "depletion_imminent"` constant
2. Update `detect_event_state()` to check depletion condition
3. Return `depletion_imminent` state when appropriate

**Event detection logic:**

```python
def _detect_depletion_imminent(
    inputs: BatteryInputs,
    prediction: BatteryPrediction
) -> bool:
    """Check if battery is approaching depletion voltage cutoff."""
    if inputs.depletion_voltage is None or prediction.usable_soc_percent is None:
        return False
    if inputs.voltage is None:
        return False
    if prediction.usable_soc_percent >= 5.0:
        return False
    if prediction.mode != MODE_DISCHARGING:
        return False
    # Must be actively discharging to trigger imminent state
    if inputs.current is not None and abs(inputs.current) < 1.0:
        return False
    return True
```

### Phase 3: Add Sensors (sensor.py)

**Changes needed:**
1. Add `BatterySensorDescription` entries for usable_soc and time_to_depletion
2. Add diagnostic sensor descriptions for configured/learned depletion voltages
3. Update sensor list tuples
4. Implement value_fn lambdas for each new sensor

**Sensor additions:**

```python
SENSORS: tuple[BatterySensorDescription, ...] = (
    # ... existing sensors ...
    BatterySensorDescription(
        key="usable_soc",
        name="Usable SOC",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.usable_soc_percent,
    ),
    BatterySensorDescription(
        key="time_to_depletion",
        name="Time to depletion",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.time_to_depletion_h,
    ),
)

DIAGNOSTICS_SENSORS: tuple[BatteryStatsSensorDescription, ...] = (
    # ... existing diagnostics ...
    BatteryStatsSensorDescription(
        key="configured_depletion_voltage",
        name="Configured depletion voltage",
        native_unit_of_measurement=UNIT_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.configured_depletion_voltage,
    ),
    BatteryStatsSensorDescription(
        key="learned_depletion_voltage",
        name="Learned depletion voltage",
        native_unit_of_measurement=UNIT_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.learned_depletion_voltage,
    ),
)
```

### Phase 4: Update Storage (storage.py)

**Changes needed:**
1. Add `configured_depletion_voltage` field to `BatteryStats`
2. Add `learned_depletion_voltage` field to `BatteryStats`
3. Add persistence logic in `to_dict()` and `from_dict()`

### Phase 5: Update Config Flow (config_flow.py)

**Changes needed:**
1. Update `strings.json` with new sensor names and descriptions
2. No config flow changes needed (depletion_voltage already configurable)

### Phase 6: Update Constants (const.py)

**Changes needed:**
1. Add constants if needed (likely none, already in place)

### Phase 7: Tests

**New test scenarios:**

```python
def test_usable_soc_below_depletion():
    """When voltage <= depletion, usable_soc = 0%"""
    
def test_usable_soc_above_full():
    """When voltage >= full_voltage, usable_soc = estimated_soc capped at 100%"""
    
def test_usable_soc_in_range():
    """Linear interpolation between depletion and full voltages"""
    
def test_time_to_depletion_discharging():
    """Calculate runtime until depletion voltage at given discharge rate"""
    
def test_time_to_depletion_charging():
    """Should return None when charging"""
    
def test_depletion_imminent_state():
    """Detect when usable_soc < 5% and actively discharging"""
    
def test_depletion_not_imminent_idle():
    """Should not trigger depletion_imminent if idle"""
```

---

## Rollout Strategy

### Week 1: Core Implementation
- [ ] Update predictor.py with usable SOC calculations
- [ ] Update events.py with depletion_imminent detection
- [ ] Update sensor.py with 4 new sensors
- [ ] Update storage.py for persistence
- [ ] Update strings.json with translations

### Week 2: Testing & Validation
- [ ] Create unit tests for all new functions
- [ ] Create integration tests with multiple battery types
- [ ] Manual testing with real battery data
- [ ] Performance testing (ensure no regressions)

### Week 3: Documentation
- [ ] Update SENSOR_REFERENCE.md with new sensors
- [ ] Update QUICK_START.md with usable SOC explanation
- [ ] Add example automations for depletion alerts
- [ ] Update README if appropriate

### Week 4: Beta Release
- [ ] Merge to main
- [ ] Tag v0.1.0-beta.2
- [ ] Release notes highlighting new feature
- [ ] Community feedback collection

---

## Backward Compatibility

✅ **Fully backward compatible**
- Existing `estimated_soc` behavior unchanged
- New sensors are optional (can be hidden)
- Config flow already supports depletion_voltage
- Depletion voltage has sensible default (96% of nominal)

---

## Risk Assessment

### Low Risk ✅
- Pure calculation functions (no external dependencies)
- New sensors don't affect existing logic
- Event detection is additive (new state only)
- Fully backward compatible

### Medium Risk ⚠️
- Need real-world validation of usable SOC calculations
- Depletion voltage learning (future phase) may need refinement
- User expectations around depletion alerts

### Mitigation
- Comprehensive unit tests
- Conservative defaults
- Clear documentation
- Community feedback channel

---

## Files to Modify

```
custom_components/battery_remaining_time/
  ├── predictor.py          (Add usable_soc, time_to_depletion functions)
  ├── events.py             (Add depletion_imminent state)
  ├── sensor.py             (Add 4 new sensors)
  ├── storage.py            (Add persistence for depletion data)
  ├── const.py              (Add new state constant)
  └── strings.json          (Add translations)

docs/
  └── SENSOR_REFERENCE.md   (Document new sensors)

QUICK_START.md               (Add depletion voltage section)
```

---

## Success Criteria

✅ **Must Have:**
1. `sensor.usable_soc` returns correct % between depletion and full
2. `sensor.time_to_depletion` calculates runtime correctly
3. `depletion_imminent` event state triggers when usable_soc < 5%
4. All unit tests pass
5. No regression in existing sensors

⚠️ **Should Have:**
1. > 90% test coverage for new code
2. Performance no worse than existing
3. Example automations in docs

🎯 **Nice to Have:**
1. Learned depletion voltage (Phase 3 enhancement)
2. Screenshots showing usable SOC on dashboard

---

## Timeline

- **Today:** Design & planning (✅ Complete)
- **Session 1:** Core implementation (predictor, events, sensors)
- **Session 2:** Testing & validation
- **Session 3:** Documentation & examples
- **Session 4:** Beta release

---

## Questions to Answer Before Implementation

1. **Depletion Voltage Default:** Use 96% of nominal or user-configurable only?
   - **Decision:** Already configurable; default = 96% * nominal voltage

2. **Learn Depletion Voltage:** Should it be adaptive?
   - **Decision:** Out of scope for Task 3; planned for Phase 3

3. **Automation Examples:** What should we document?
   - **Decision:** Low battery warning, cutoff imminent alert, etc.

4. **Sensor Enable Default:** Should usable_soc be visible by default?
   - **Decision:** Yes (primary use case for inverter users)

---

## Next Action

Ready to implement Phase 1: Core predictor functions.

Should I proceed with updating predictor.py with the new functions?
