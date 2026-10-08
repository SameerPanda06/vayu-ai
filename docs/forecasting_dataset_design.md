# Vayu AI — Forecasting Dataset Design & Supervised Learning Specification

**Phase 4 Step 1: Architectural Design Specification**  
*Coupled Atmospheric Chemistry & Weather Forecasting for Delhi NCR*

---

## 1. Overview & Objectives

This document formalizes the mathematical design, feature taxonomy, and anti-leakage guarantees for constructing supervised tabular and time-series forecasting datasets in Vayu AI.

The forecasting objective is multi-step atmospheric pollution prediction for Delhi NCR monitoring stations over three operationally significant planning horizons:
- **T+24 hours:** Short-term diurnal emergency response and nocturnal particulate inversion anticipation.
- **T+48 hours:** Tactical decision support for episodic traffic interventions, construction bans, and school advisories (GRAP Stages I–IV).
- **T+72 hours:** Regional synoptic coupled chemistry-weather outlook.

> [!IMPORTANT]
> **Strict Non-Imputation and Provenance Policy:**  
> 1. Official CPCB monitoring station observations (`air_quality_readings`) and numerical reanalysis estimates (`modeled_air_quality_estimates`) reside in completely separate persistence layers and are never mixed.
> 2. Missing observation hours and sensor dropouts are strictly marked as `None`/`null`. They are **never** silently zeroed or linearly interpolated, which would corrupt atmospheric variance and lead to spurious ML weights.

---

## 2. Target Variables & Horizons

Let $t_0$ denote the forecast issue time (anchor step).

### Primary Continuous Target
- **$\text{PM}_{2.5}$ Mass Concentration ($\mu\text{g/m}^3$):**  
  Primary target for continuous regression. Fine particulate matter represents the dominant public health hazard and episodic winter trapping pollutant across Delhi NCR.

### Horizon Targets Formulated
For each sample at reference time $t_0$, the target vector $Y_{t_0}$ comprises:
$$Y_{t_0} = \begin{bmatrix} y_{t_0 + 24} \\ y_{t_0 + 48} \\ y_{t_0 + 72} \end{bmatrix}$$
where:
- $\text{target\_pm2\_5\_h24} = y_{t_0 + 24}$
- $\text{target\_pm2\_5\_h48} = y_{t_0 + 48}$
- $\text{target\_pm2\_5\_h72} = y_{t_0 + 72}$

---

## 3. Feature Taxonomy & Mathematical Definitions

All features for sample $t_0$ are computed strictly using historical and current measurements: $t \le t_0$.

### 3.1 Autoregressive Lag Features
Atmospheric particulate accumulation exhibits strong persistence and multiscale memory. The lag vector incorporates short-term inertia and diurnal recurrence:
$$\mathcal{L}_{\text{target}}(t_0) = \{ y_{t_0 - k} \mid k \in \{1, 2, 3, 6, 12, 24, 48, 72\} \}$$
- **$k \in \{1, 2, 3\}$:** Immediate hour-to-hour persistence and sensor trajectory.
- **$k = 6$:** Sub-diurnal boundary layer transition (morning rush hour to afternoon convective mixing).
- **$k = 12$:** Day/night inversion phase shift (nocturnal surface inversion trapping vs daytime solar ventilation).
- **$k \in \{24, 48, 72\}$:** 24-hour diurnal cyclical recurrence and multi-day synoptic stagnation memory.

### 3.2 Co-Pollutant Coupling Features
Atmospheric chemistry coupling dictates that particulate formation is coupled with precursor and combustion gases ($\text{NO}_2, \text{SO}_2, \text{CO}, \text{O}_3, \text{PM}_{10}$):
$$\mathcal{L}_{\text{copoll}}(t_0) = \{ p_{t_0}, p_{t_0 - 1}, p_{t_0 - 6}, p_{t_0 - 24} \mid p \in \{\text{PM}_{10}, \text{NO}_2, \text{SO}_2, \text{CO}, \text{O}_3\} \}$$
- **Carbon Monoxide ($\text{CO}$):** Ingested in $\mu\text{g/m}^3$ from Open-Meteo and strictly normalized to $\text{mg/m}^3$ ($\text{CO} / 1000$). Serves as an inert tracer of vehicular combustion.
- **$\text{PM}_{10} / \text{PM}_{2.5}$ Ratio:** Proxies coarse dust vs fine secondary aerosol fractions.
- **$\text{O}_3$ and $\text{NO}_2$ Photochemical Couple:** Captures daylight photochemical smog kinetics.

### 3.3 Backward Rolling Window Statistics
Non-stationary atmospheric regimes require statistical summaries of recent volatility and baseline trends over sliding past windows $W \in \{6\text{h}, 12\text{h}, 24\text{h}\}$:
$$\mu_{W}(t_0) = \frac{1}{|W|} \sum_{s=0}^{W-1} y_{t_0 - s}$$
$$\sigma_{W}(t_0) = \sqrt{\frac{1}{|W|-1} \sum_{s=0}^{W-1} (y_{t_0 - s} - \mu_W(t_0))^2}$$
$$\min_{W}(t_0) = \min_{s \in [0, W-1]} y_{t_0 - s}, \quad \max_{W}(t_0) = \max_{s \in [0, W-1]} y_{t_0 - s}$$

### 3.4 Periodic Diurnal & Calendar Encodings
To avoid step discontinuities at midnight and year-end, cyclical temporal features are mapped onto orthogonal unit circles:
$$\text{hour\_sin}(t_0) = \sin\left(\frac{2\pi \cdot \text{hour}}{24}\right), \quad \text{hour\_cos}(t_0) = \cos\left(\frac{2\pi \cdot \text{hour}}{24}\right)$$
$$\text{month\_sin}(t_0) = \sin\left(\frac{2\pi \cdot \text{month}}{12}\right), \quad \text{month\_cos}(t_0) = \cos\left(\frac{2\pi \cdot \text{month}}{12}\right)$$
$$\text{day\_of\_week}(t_0) \in \{0, \dots, 6\}, \quad \text{is\_weekend}(t_0) \in \{0, 1\}$$

---

## 4. Anti-Leakage Guarantees

In atmospheric forecasting, subtle look-ahead bias invalidates model evaluation. Vayu AI implements 5 strict anti-leakage rules:

```text
Historical Timeline:
[================ TRAIN ================]  |-- 72h EMBARGO --|  [====== VAL ======]  |-- 72h EMBARGO --|  [====== TEST ======]
                 t <= T_train_end                               T_val_start <= t                         T_test_start <= t
                                  (No target overlap)                                    (No target overlap)
```

1. **Strict Temporal Partitioning:** Dataset is partitioned chronologically (e.g. 70% Train, 15% Validation, 15% Test). Random shuffling (`train_test_split(shuffle=True)`) is strictly forbidden.
2. **Horizon Embargo Gap:** Samples within the 72 hours immediately preceding the validation split are purged from the training set. Because training targets at $t_0$ look ahead up to $t_0 + 72\text{h}$, an un-embargoed split would allow training targets to overlap with evaluation feature states.
3. **Causal Point-in-Time Rolling Statistics:** Rolling means, minimums, maximums, and standard deviations are computed backward-in-time ($t \le t_0$). Centered rolling windows ($\pm 12\text{h}$) are forbidden.
4. **Pre-processing Normalization Isolation:** Feature scaling statistics (mean, variance, min-max bounds) must be fitted strictly on the Training split and applied transformatively to Validation and Test splits.
5. **No Target Contamination:** Target names (`target_pm2_5_h24`, `target_pm2_5_h48`, `target_pm2_5_h72`) are never present in the input feature dictionary.

---

## 5. Dataset Completeness & Missing Hours Diagnostics

The dataset preparation module ([dataset_builder.py](file:///c:/Users/patra/OneDrive/Pictures/Desktop/vayu-ai/backend/app/services/dataset_builder.py)) generates a quality report on each extraction:
- $\text{Total Expected Steps} = \left\lfloor \frac{t_{\text{end}} - t_{\text{start}}}{3600} \right\rfloor + 1$
- $\text{Completeness (\%)} = \frac{\text{Available Observations}}{\text{Total Expected Steps}} \times 100\%$
- Field-level null tracking across all pollutants.
- Duplicate timestamp detection and rejection.
