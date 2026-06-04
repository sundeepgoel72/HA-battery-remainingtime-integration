# Sensor Reference Guide

Complete reference for all Battery Remaining Time sensors and their attributes.

---

## Main Sensors

These are the primary sensors created for every battery instance.

### 1. Estimated SOC
**Entity ID:** `sensor.{battery_name}_estimated_soc`  
**Type:** Percentage (0-100%)  
**Unit:** `%`  
**Update Frequency:** Every update interval (default 60s)

**Description:** The integrated battery State of Charge based on the selected algorithm.

**Attributes:**
- `algorithm` - The algorithm used for this estimate
- `soc_percent` - Numeric SOC value
- `mode` - Operating mode (charging/discharging/idle)
- `confidence` - Prediction confidence (`very_low`/`low`/`medium`/`high`)
- `event_state` - Battery operating state (resting/charging/discharging/float/etc)
- `battery_type` - Configured battery chemistry
- `battery_brand_model` - Optional brand/model identifier
- `calibration_anchor` - If at a known reference point

### 2. Time to Empty
**Entity ID:** `sensor.{battery_name}_time_to_empty`  
**Type:** Duration  
**Unit:** `h` (hours)  
**Update Frequency:** Every update interval

**Description:** Estimated hours remaining until battery is fully discharged at current discharge rate.

**Attributes:** Same as Estimated SOC

**Notes:**
- Value is `None` if battery is charging or idle
- Becomes less accurate at very high or very low SOC
- Uses multiple algorithms for robustness

### 3. Time to Full
**Entity ID:** `sensor.{battery_name}_time_to_full`  
**Type:** Duration  
**Unit:** `h` (hours)  
**Update Frequency:** Every update interval

**Description:** Estimated hours remaining until battery is fully charged at current charge rate.

**Attributes:** Same as Estimated SOC

**Notes:**
- Value is `None` if battery is discharging or idle
- Only calculated when active charging detected
- Accounts for multi-stage charging profiles

### 4. Net Power
**Entity ID:** `sensor.{battery_name}_net_power`  
**Type:** Power  
**Unit:** `W` (Watts)  
**Update Frequency:** Every update interval

**Description:** Current power flow: positive for charging, negative for discharging.

**Attributes:**
- All standard attributes from Estimated SOC
- Plus power-specific metadata

### 5. Mode
**Entity ID:** `sensor.{battery_name}_mode`  
**Type:** String  
**Values:** `charging`, `discharging`, `idle`, `unknown`

**Description:** Current operating mode detected from sensor telemetry.

### 6. Confidence
**Entity ID:** `sensor.{battery_name}_confidence`  
**Type:** String  
**Values:** `very_low`, `low`, `medium`, `high`

**Description:** Confidence level in the current prediction.

**Factors affecting confidence:**
- Number of historical observations
- Calibration anchor events (rest, low battery, float)
- Algorithm agreement (spread)
- Sensor availability
- System uptime

**Spread thresholds:**
- `high` when spread is `<= 5%`
- `medium` when spread is `<= 15%`
- `low` when spread is `<= 30%`
- `very_low` when spread is `> 30%`

---

## Comparison Sensors

These sensors are exposed for field debugging and model observability during the current beta cycle.

### SOC Comparison Sensors

- `sensor.{battery_name}_soc_ocv`
- `sensor.{battery_name}_soc_coulomb`
- `sensor.{battery_name}_soc_peukert`
- `sensor.{battery_name}_soc_hybrid`
- `sensor.{battery_name}_soc_ensemble`

### TTE Comparison Sensors

- `sensor.{battery_name}_tte_ocv`
- `sensor.{battery_name}_tte_coulomb`
- `sensor.{battery_name}_tte_peukert`
- `sensor.{battery_name}_tte_hybrid`
- `sensor.{battery_name}_tte_ensemble`

### TTF Comparison Sensors

- `sensor.{battery_name}_ttf_ocv`
- `sensor.{battery_name}_ttf_coulomb`
- `sensor.{battery_name}_ttf_peukert`
- `sensor.{battery_name}_ttf_hybrid`
- `sensor.{battery_name}_ttf_ensemble`

**Attributes exposed on comparison sensors:**
- `algorithm`
- `confidence`
- `reason`
- `mode`
- `algorithm_spread`
- `active_algorithm`
- `source_evidence_status`

### 7. Algorithm
**Entity ID:** `sensor.{battery_name}_algorithm`  
**Type:** String  
**Values:** Algorithm name selected in configuration

**Description:** Active prediction algorithm (e.g., "ensemble", "hybrid_lead_acid", etc)

---

## Health & Statistics Sensors

These diagnostic sensors track battery learning and health metrics. They're disabled by default but can be enabled in entity settings.

### Battery Health
**Entity ID:** `sensor.{battery_name}_battery_health`  
**Type:** Percentage (0-100%)  
**Unit:** `%`  
**Category:** Diagnostic

**Description:** Estimated current battery health based on capacity retention and cycle count.

**How it's calculated:**
- Tracks capacity degradation over time
- Combines cycle count and calendar aging
- Self-calibrates from real discharge curves

**Attributes:**
- `health_confidence` - Confidence in health estimate
- `health_observation_count` - Number of calibration events
- `configured_capacity_ah` - Original battery capacity
- `learned_capacity_ah` - Current measured capacity

### Learned Capacity
**Entity ID:** `sensor.{battery_name}_learned_capacity`  
**Type:** Electric Charge  
**Unit:** `Ah` (Amp-hours)  
**Category:** Diagnostic

**Description:** Actual measured battery capacity vs. configured capacity.

**Use cases:**
- Detect aging batteries
- Validate initial capacity configuration
- Track capacity loss over time

**Attributes:**
- `capacity_confidence` - How confident we are in this measurement
- `capacity_observation_count` - Number of observations
- `capacity_retention_percent` - % of original capacity remaining

### Capacity Retention
**Entity ID:** `sensor.{battery_name}_capacity_retention`  
**Type:** Percentage (0-100%)  
**Unit:** `%`  
**Category:** Diagnostic

**Description:** Percentage of original capacity still available.

**Example:**
- Configured: 200 Ah
- Learned: 160 Ah
- Retention: 80%

### Battery Useful Life
**Entity ID:** `sensor.{battery_name}_battery_useful_life`  
**Type:** Percentage (0-100%)  
**Unit:** `%`  
**Category:** Diagnostic

**Description:** Estimated remaining useful life considering both capacity and cycle aging.

### Equivalent Cycles
**Entity ID:** `sensor.{battery_name}_equivalent_cycles`  
**Type:** Numeric  
**Unit:** `cycles`  
**Category:** Diagnostic

**Description:** Total equivalent full charge/discharge cycles completed.

**Notes:**
- Partial cycles are weighted appropriately
- Resets after configuration changes
- Used for end-of-life prediction

### Health Confidence
**Entity ID:** `sensor.{battery_name}_health_confidence`  
**Type:** String  
**Values:** `low`, `medium`, `high`  
**Category:** Diagnostic

**Description:** Confidence level in health estimate.

### Remaining Cycles
**Entity ID:** `sensor.{battery_name}_remaining_cycles`  
**Type:** Numeric  
**Unit:** `cycles`  
**Category:** Diagnostic

**Description:** Estimated cycles remaining before end-of-life.

**Calculation:**
- Expected cycle life (battery type dependent)
- Minus equivalent cycles already used
- Provides replacement planning window

### Remaining Life
**Entity ID:** `sensor.{battery_name}_remaining_life`  
**Type:** Percentage (0-100%)  
**Unit:** `%`  
**Category:** Diagnostic

**Description:** Overall remaining battery life percentage.

**Factors:**
- Cycle degradation
- Capacity retention
- Estimated aging curve for battery type

---

## Peukert Learning Sensors

These sensors track the learned Peukert exponent, a critical parameter for discharge time estimation.

### Learned Peukert Exponent
**Entity ID:** `sensor.{battery_name}_learned_peukert_exponent`  
**Type:** Float  
**Default:** 1.3 (lead-acid typical)  
**Category:** Diagnostic

**Description:** Adaptive Peukert exponent learned from observed discharge behavior.

**What it means:**
- Value > 1.3: Battery runtime varies significantly with discharge rate
- Value ≈ 1.3: Standard lead-acid behavior
- Value < 1.3: Better high-rate discharge performance

### Peukert Confidence
**Entity ID:** `sensor.{battery_name}_peukert_confidence`  
**Type:** String  
**Values:** `low`, `medium`, `high`  
**Category:** Diagnostic

**Description:** Confidence in the learned Peukert exponent.

**Confidence progression:**
- **low:** < 3 observations, uses default (1.3)
- **medium:** 3-20 observations, blends default with learned
- **high:** > 20 observations, fully uses learned value

### Peukert Observation Count
**Entity ID:** `sensor.{battery_name}_peukert_observation_count`  
**Type:** Numeric  
**Unit:** `observations`  
**Category:** Diagnostic

**Description:** Number of discharge cycles used to learn Peukert exponent.

**Notes:**
- Increments on calibration anchor events (low battery detected)
- Better accuracy with more observations
- Resets on configuration changes

---

## Prediction Quality Sensors

### Prediction Health
**Entity ID:** `sensor.{battery_name}_prediction_health`  
**Type:** String  
**Values:** `ok`, `limited`, `degraded`, `divergent`  
**Category:** Diagnostic

**Description:** Overall health indicator for prediction quality.

**Status Meanings:**
- `ok` - Predictions are reliable
- `limited` - Predictions work but confidence is lower
- `degraded` - Predictions may be inaccurate
- `divergent` - Algorithms disagree significantly

**Attributes:**
- `confidence_score` - 0-100 numeric score
- `algorithm_spread` - Percentage spread between algorithms
- `algorithm_stddev` - Standard deviation across models
- `algorithm_outlier` - Model furthest from consensus (if any)
- `model_outputs` - Per-model SOC values
- `event_state` - Battery operating state
- `calibration_anchor` - At known reference point

### Calibration Status
**Entity ID:** `sensor.{battery_name}_calibration_status`  
**Type:** Percentage (0-100%)  
**Unit:** `%`  
**Category:** Diagnostic

**Description:** Readiness score for calibration - how much evidence has been collected.

**Scoring:**
- Rest events: +3% each (max 30%)
- Float events: +3% each (max 30%)
- Absorption events: +2% each (max 20%)
- Low battery events: +4% each (max 20%)
- Total: 0-100%

**Use:** High calibration status means learned values are trustworthy.

### Algorithm Spread
**Entity ID:** `sensor.{battery_name}_algorithm_spread`  
**Type:** Percentage (0-100%)  
**Unit:** `%`  
**Category:** Diagnostic

**Description:** Standard deviation of SOC estimates across all algorithms.

**Interpretation:**
- < 2%: Excellent consensus
- 2-5%: Good consensus
- 5-10%: Acceptable
- 10-20%: Notable divergence
- > 20%: Algorithms disagree significantly

### Model Accuracy
**Entity ID:** `sensor.{battery_name}_model_accuracy`  
**Type:** Percentage (0-100%)  
**Unit:** `%`  
**Category:** Diagnostic

**Description:** Summary score for learned model-accuracy convergence across calibration anchors.

**Attributes:**
- `average_accuracy` - Mean learned accuracy across calibrated models
- `best_model` - Highest-scoring learned model
- `worst_model` - Lowest-scoring learned model
- `learned_model_count` - Number of models with accuracy history
- `model_accuracy` - Per-model accuracy map
- `confidence_score` - Overall operational confidence score
- `algorithm_spread` - Current spread at the time of reporting
- `source_evidence_status` - `live`, `recorder_fallback`, or `insufficient`

---

## Model Comparison Visibility

The integration exposes only the selected algorithm result as primary Home Assistant entities to keep the entity list manageable.

Alternate model outputs remain available through:

- `algorithm_spread` diagnostic attributes
- `prediction_health` diagnostic attributes
- `calibration_status` diagnostic attributes
- Home Assistant debug logs from `custom_components.battery_remaining_time.coordinator`

The relevant diagnostic attributes include:

- `model_outputs`
- `model_accuracy`
- `model_weighting`
- `ensemble_weights`
- `algorithm_outlier`
- `algorithm_stddev`

---

## Learned Voltage Sensors (Beta Features)

*These sensors are part of Phase 3 enhancements.*

### Learned Full Voltage
**Entity ID:** `sensor.{battery_name}_learned_full_voltage`  
**Type:** Voltage  
**Unit:** `V`  
**Category:** Diagnostic

**Description:** Voltage at 100% SOC as learned from observations.

### Learned Empty Voltage
**Entity ID:** `sensor.{battery_name}_learned_empty_voltage`  
**Type:** Voltage  
**Unit:** `V`  
**Category:** Diagnostic

**Description:** Voltage at 0% SOC as learned from observations.

### Learned Charge Efficiency
**Entity ID:** `sensor.{battery_name}_learned_charge_efficiency`  
**Type:** Percentage (0-100%)  
**Unit:** `%`  
**Category:** Diagnostic

**Description:** Measured charge efficiency accounting for losses.

### Usable SOC / Depletion Voltage Sensors
**Entity ID:** `sensor.{battery_name}_usable_soc`  
**Type:** Percentage (0-100%)  
**Unit:** `%`  
**Category:** Primary

**Description:** Practical SOC above the configured or learned depletion voltage.

**Entity ID:** `sensor.{battery_name}_time_to_depletion`  
**Type:** Duration  
**Unit:** `h`  
**Category:** Primary

**Description:** Runtime remaining until the depletion voltage is reached.

**Entity ID:** `sensor.{battery_name}_configured_depletion_voltage`  
**Type:** Voltage  
**Unit:** `V`  
**Category:** Diagnostic

**Description:** Configured depletion-voltage cutoff from the config entry.

**Entity ID:** `sensor.{battery_name}_learned_depletion_voltage`  
**Type:** Voltage  
**Unit:** `V`  
**Category:** Diagnostic

**Description:** Learned depletion-voltage cutoff from low-battery and depletion-imminent anchors.

**Entity ID:** `sensor.{battery_name}_depletion_voltage_confidence`  
**Type:** Text  
**Category:** Diagnostic

**Description:** Confidence level for the learned depletion-voltage cutoff.

---

## Automation Examples

### Alert when battery is low
```yaml
automation:
  - alias: Battery Low Alert
    trigger:
      entity_id: sensor.battery_time_to_empty
      below: 1.0
    action:
      service: persistent_notification.create
      data:
        title: Battery Warning
        message: "Battery will be depleted in less than 1 hour"
```

### Notify before discharge cutoff
```yaml
automation:
  - alias: Battery Discharge Cutoff Alert
    trigger:
      entity_id: sensor.battery_estimated_soc
      below: 20
    condition:
      - condition: state
        entity_id: sensor.battery_mode
        state: "discharging"
    action:
      service: notify.mobile_app
      data:
        title: Discharge Cutoff Alert
        message: "Battery SOC is {{ states('sensor.battery_estimated_soc') }}%"
```

### Monitor calibration progress
```yaml
automation:
  - alias: Check Calibration Progress
    trigger:
      platform: time_pattern
      hours: "12"
    action:
      service: persistent_notification.create
      data:
        title: Calibration Status
        message: "Calibration at {{ states('sensor.battery_calibration_status') }}%"
```

---

## Troubleshooting by Sensor

| Symptom | Check These Sensors | Action |
|---------|-------------------|--------|
| SOC stuck at one value | algorithm_spread, prediction_health | Verify sensors are updating |
| Confidence always "low" | calibration_status, peukert_confidence | Run calibration cycles |
| TTE/TTF shows None | battery_mode | Mode should be discharging/charging |
| Health shows 0% | learned_capacity, equivalent_cycles | Verify capacity configuration |
| Algorithms diverge > 20% | per-model SOC sensors | Check for sensor noise |

---

## Best Practices

1. **Monitor calibration_status** - Don't rely on confidence until > 60%
2. **Use prediction_health** for alerts - More reliable than individual metrics
3. **Enable per-model SOC** temporarily to debug divergence
4. **Track learned_capacity** - Helps predict end-of-life
5. **Check peukert_confidence** - High confidence = accurate TTE at various rates
