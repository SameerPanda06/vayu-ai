# Vayu AI (SIH26082)

**Air Pollution–Weather Coupled Forecasting System for Delhi NCR**  
*Phase 1 Foundation: Architecture, Contracts, & Runnable Verification*

---

> [!IMPORTANT]
> **Synthetic Demo Disclaimer:**  
> Phase 1 provides a clean, runnable architectural foundation and interface contract. All forecast values displayed in this phase are **deterministic, illustrative synthetic series**. They do **not** represent live ground monitoring observations, validated predictions, an operational ML emulator, or coupled WRF-Chem chemistry runs. PM2.5 is reported strictly as mass concentration in $\mu\text{g/m}^3$ and is **never** labeled as AQI.

---

## 1. Project Overview

Vayu AI is being engineered to tackle the severe, episodic winter air pollution events across the National Capital Region (Delhi NCR). The full production vision combines:
- Ingestion of continuous ambient air quality stations (CAAQMS) and operational numerical weather prediction (NWP) outputs.
- High-resolution physical simulation of chemistry-transport and aerosol-radiation feedbacks (WRF-Chem).
- Atmospheric diagnostics (planetary boundary layer height, nocturnal inversion trapping, ventilation coefficient).
- Physics-informed machine learning bias correction and surrogate neural emulators.
- Decision support for episodic interventions and scenario testing.

- Physics-informed machine learning bias correction and surrogate neural emulators.
- Decision support for episodic interventions and scenario testing.

**Phase 2 implements the polished Delhi NCR Air-Quality Exploration Dashboard:**
- Deep navy background, restrained teal accents, high-contrast readable typography.
- Compact header with Vayu AI branding, Delhi NCR context, and a data-mode badge.
- Concise persistent notice: *“Demo mode · Synthetic data · Not a validated forecast.”*
- Interactive Leaflet map of Delhi NCR with discrete station markers, concentration color scales (strictly not AQI), and public CartoDB/OSM basemap attribution.
- Synchronized single-hour state across summary cards, map tooltips, station details, and the 72-hour SVG chart.
- Session forecast caching for instant station switching without redundant network requests.
- Accessible previous/next hour step buttons and strict T+0h to T+71h slider labeling.
- Data Provenance panel detailing simulation assumptions, limitations, and future roadmap.

---

## 2. Directory Structure

```text
vayu-ai/
├── backend/
│   ├── app/
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── forecast.py          # GET /api/forecast?station_id=...
│   │   │   ├── health.py            # GET /api/health
│   │   │   └── stations.py          # GET /api/stations
│   │   ├── __init__.py
│   │   ├── config.py                # Settings & CORS configuration
│   │   ├── main.py                  # FastAPI application setup
│   │   ├── schemas.py               # Pydantic data schemas
│   │   ├── stations.py              # Delhi NCR stations metadata
│   │   └── synthetic.py             # Deterministic 72h physics-inspired series generator
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_forecast.py         # Tests 72h records, determinism, units, bounds
│   │   ├── test_health.py           # Tests health and version status
│   │   └── test_stations.py         # Tests station directory coverage
│   ├── pyproject.toml               # Pytest configuration
│   └── requirements.txt             # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── DataProvenancePanel.tsx # Explanatory panel for data origins & scope
│   │   │   ├── DelhiMap.tsx            # Leaflet map with discrete station points & legend
│   │   │   ├── ForecastChart.tsx       # Interactive 72-hour SVG chart + synchronized slider
│   │   │   ├── Header.tsx              # Compact branding, Delhi NCR context, mode badge
│   │   │   ├── Icons.tsx               # Crisp SVG icons (no emojis)
│   │   │   ├── LocationTimeBar.tsx     # Station selector and time stepper controls
│   │   │   ├── NoticeBanner.tsx        # Concise persistent demo disclaimer
│   │   │   ├── StationDetailPanel.tsx  # Selected station characteristics & conditions
│   │   │   ├── StatusView.tsx          # Loading, error, and empty state handler
│   │   │   └── SummaryCards.tsx        # Four summary cards with scientific labels
│   │   ├── styles/
│   │   │   └── index.css            # Deep navy & teal theme, responsive breakpoints
│   │   ├── api.ts                   # Frontend API client
│   │   ├── App.tsx                  # Root state coordination & session cache
│   │   ├── main.tsx                 # React DOM mount point
│   │   ├── types.ts                 # TypeScript response & station interfaces
│   │   └── vite-env.d.ts            # Client environment types
│   ├── index.html                   # HTML shell with Inter typography
│   ├── package.json                 # Frontend dependencies (React, Leaflet, Vite, TS)
│   ├── tsconfig.json                # Strict TypeScript configuration
│   ├── tsconfig.node.json           # Node/Vite build config
│   └── vite.config.ts               # Vite dev server with /api proxy
├── docs/
│   └── architecture.md              # Coupling architecture & system flow
├── .env.example                     # Environment configuration template
├── .gitignore                       # Git ignore rules
└── README.md                        # Project documentation
```

---

## 3. Prerequisites

- **Python:** Version 3.11 or 3.12+
- **Node.js:** Version 18+ (tested on Node v20/v24)
- **npm:** Version 9+

*No Docker, Redis, PostGIS, cloud services, or external API keys are required for Phase 1.*

---

## 4. Setup Instructions

### Step 1: Clone Repository
```bash
git clone https://github.com/SameerPanda06/vayu-ai.git
cd vayu-ai
```

### Step 2: Environment Configuration
Copy the template configuration files:

**Windows PowerShell:**
```powershell
Copy-Item .env.example .env
Copy-Item .env.example frontend\.env
```

**macOS / Linux:**
```bash
cp .env.example .env
cp .env.example frontend/.env
```

---

### Step 3: Backend Setup

#### Windows PowerShell:
```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

#### macOS / Linux:
```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r backend/requirements.txt
```

---

### Step 4: Frontend Setup
```bash
cd frontend
npm install
cd ..
```

---

## 5. Running the Application Locally

Run the backend and frontend in two separate terminal windows.

### Terminal 1: Backend API Service

**Windows PowerShell:**
```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

**macOS / Linux:**
```bash
source .venv/bin/activate
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

- API Base: `http://127.0.0.1:8000/api`
- Interactive Swagger Docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/api/health`

---

### Terminal 2: Frontend Dev Server

```bash
cd frontend
npm run dev
```

- Web Dashboard: `http://127.0.0.1:5173`

---

## 6. Running Tests & Quality Checks

### Run Backend Pytest Suite

**Windows PowerShell:**
```powershell
.\.venv\Scripts\pytest backend/tests
```

**macOS / Linux:**
```bash
source .venv/bin/activate
pytest backend/tests
```

### Run Frontend Typecheck & Production Build
```bash
cd frontend

# Verify TypeScript types without emitting files
npm run typecheck

# Execute production bundle build
npm run build
```

---

## 7. API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health status, version, and server timestamp |
| `GET` | `/api/stations` | List of supported Delhi NCR monitoring stations |
| `GET` | `/api/forecast?station_id={id}` | Exactly 72 hourly synthetic forecast records + metadata |

### Sample Response (`GET /api/forecast?station_id=anand-vihar`)
```json
{
  "data_mode": "synthetic_demo",
  "statement": "Synthetic demo series for Phase 1 interface and contract validation. These values are illustrative, deterministic, and unvalidated. They do NOT represent actual atmospheric observations or certified predictions.",
  "generated_at": "2026-10-06T00:00:00Z",
  "units": {
    "pm25": "µg/m³",
    "temperature": "°C",
    "wind_speed": "m/s",
    "pbl_height": "m"
  },
  "station": {
    "id": "anand-vihar",
    "name": "Anand Vihar",
    "city": "Delhi NCR",
    "state": "Delhi",
    "latitude": 28.6469,
    "longitude": 77.3160,
    "elevation_m": 215.0,
    "description": "East Delhi transport hub with inter-state bus terminal and rail corridor; frequent nocturnal particulate trapping."
  },
  "forecast_hours": 72,
  "forecast": [
    {
      "hour_index": 0,
      "timestamp_utc": "2026-10-06T00:00:00Z",
      "pm25": 178.4,
      "temperature_c": 17.5,
      "wind_speed_ms": 1.7,
      "pbl_height_m": 294.0
    }
  ]
}
```

---

## 8. Current Limitations & Data Disclosures (Phase 2)

1. **Synthetic Demo Data Only:** All forecast values are deterministic mathematical series generated from fixed reference timestamps and seeds for interface verification; they do **not** represent live observations or verified predictions.
2. **Offline Execution:** No real-time ingestion from CPCB, SAFAR, DPCC, or IMD APIs. In future data integrations, the system will never silently substitute synthetic data for failed live data requests.
3. **No Numerical Coupling:** WRF-Chem chemistry and aerosol-radiation feedbacks are not yet coupled.
4. **No Trained ML Model:** The machine learning emulator and residual bias-correction layer will be introduced in subsequent phases.
5. **No Official AQI Calculation:** Values represent raw mass concentration in $\mu\text{g/m}^3$ and are not converted into single-pollutant or composite AQI index values.

---

## 9. Map & Database Architecture Specifications

### Basemap Usage Policy & Constraints
- **Public Tiles:** Employs CartoDB Voyager tiles with attribution to OpenStreetMap contributors and CARTO.
- **On-Demand Browsing:** Tiles are requested dynamically per standard browser HTTP caching. No bulk prefetching or offline scraping is performed.
- **Tile Failure Resiliency:** Should external map tile servers be unreachable (e.g., offline environments), the UI presents a concise non-blocking notice while keeping all discrete station coordinates fully clickable and interactive.

### Planned Persistence: PostgreSQL
- **PostgreSQL (with PostGIS)** is the designated persistence layer for the next data-integration phase.
- **SQLite is strictly prohibited** to prevent schema drift, ensure geospatial query parity (ST_DWithin, spatial indexing), and support production-grade time-series partitioning.

---

---

## 10. Air Quality Ingestion & Open-Meteo Fallback (Phase 3 Steps 3 & 4)

### 10.1 Data Sources & Provenance Architecture
Vayu AI maintains a strict, uncompromised separation between ground-truth observations and numerical model estimates:

| Source Type | Provider / Platform | Table | Primary Pollutants | Nature & Usage |
| :--- | :--- | :--- | :--- | :--- |
| **Primary Observation** | CPCB / MoEFCC via [data.gov.in](https://data.gov.in) | `air_quality_readings` | PM2.5, PM10, NO2, SO2, CO, O3, CPCB AQI | Official physical ground monitoring observations from continuous CAAQMS stations. Ground truth. |
| **Development Fallback** | [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api) | `modeled_air_quality_estimates` | PM2.5, PM10, NO2, SO2, CO, O3 | Numerical reanalysis / atmospheric chemistry model outputs. Non-ground-truth development surrogate. |
| **Synthetic Demo Forecast** | Vayu AI Synthetic Physics Model | `forecasts` (Phase 1/2 UI contract) | PM2.5, T, Wind, PBL | Illustrative deterministic 72h series for interface validation. |

> [!WARNING]
> **Data Provenance Guarantee:** Modeled atmospheric estimates from Open-Meteo are **never** inserted into `air_quality_readings` or mixed with official CPCB observations. Modeled values are **never** labeled as official measurements, and an Indian CPCB AQI is **never** calculated from modeled estimates.

### 10.2 Environment Configuration
Configure your `.env` for ingestion orchestration:
```ini
# Air Quality Ingestion Source Mode ('cpcb', 'open_meteo', or 'auto')
AQI_INGESTION_SOURCE=auto

# Primary Data Source: Official Data.gov.in CPCB Real-time Air Quality API
DATA_GOV_IN_API_KEY=your_api_key_here
DATA_GOV_IN_RESOURCE_ID=3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69
DATA_GOV_IN_BASE_URL=https://api.data.gov.in/resource
DATA_GOV_IN_TIMEOUT_SECONDS=15.0

# Development Fallback: Open-Meteo Air Quality API (Zero cost, no key required)
OPEN_METEO_BASE_URL=https://air-quality-api.open-meteo.com/v1/air-quality
OPEN_METEO_TIMEOUT_SECONDS=15.0
OPEN_METEO_PAST_HOURS=6
OPEN_METEO_FORECAST_HOURS=1
```

### 10.3 Database Migrations
Vayu AI uses additive, non-destructive SQL migrations to manage table schemas:
```powershell
# From repository root:
.\.venv\Scripts\python -m backend.app.scripts.migrate

# Or from backend/ directory:
python -m app.scripts.migrate
```
This safely creates the `modeled_air_quality_estimates` table and its composite uniqueness constraint `uq_modeled_estimate_station_provider_time` without dropping or modifying existing tables.

### 10.4 Running Ingestion via CLI
Execute ingestion in any of the three supported source modes:

#### 1. Automatic Fallback Ingestion (Recommended for Development)
Tries official CPCB first; on genuine network failures (e.g. `api.data.gov.in` connection refusals, timeouts, or 5xx outages), automatically falls back to Open-Meteo:
```powershell
python -m backend.app.scripts.ingest_aqi --source auto
```

#### 2. Open-Meteo Only Ingestion
Directly queries Open-Meteo atmospheric chemistry estimates for all Delhi NCR stations (requires zero external API keys):
```powershell
python -m backend.app.scripts.ingest_aqi --source open_meteo
```

#### 3. CPCB Only Ingestion
Strictly queries official CPCB data from `data.gov.in` (fails with clear error if upstream host is unreachable; will not fall back):
```powershell
python -m backend.app.scripts.ingest_aqi --source cpcb
```

Sample Output (Automatic Fallback):
```text
CPCB API primary source unreachable (Connection failure communicating with data.gov.in: [WinError 10061] No connection could be made because the target machine actively refused it). Activating Open-Meteo development fallback.
=== Vayu AI: Air Quality Data Ingestion ===
Selected source mode: auto
Actual provider used: open-meteo
API records fetched: 42
Normalized observations or estimates: 42
Stations touched: 6
Inserted rows: 42
Duplicates skipped: 0
Fallback notice: CPCB primary unavailable; fell back to Open-Meteo.
==========================================
```

### 10.5 Unit Normalization & Timestamp Standards
1. **Carbon Monoxide (CO) Unit Conversion:** Open-Meteo provides CO concentrations in $\mu\text{g/m}^3$. The internal schema standardizes CO to $\text{mg/m}^3$ to align with Indian National Ambient Air Quality Standards (NAAQS). During normalization:
   $$\text{CO}_{\text{mg/m}^3} = \frac{\text{CO}_{\mu\text{g/m}^3}}{1000}$$
2. **UTC Timestamps:** All timestamps from Open-Meteo are parsed explicitly as timezone-aware UTC datetime objects.
3. **Missing Value Sanitization:** Nulls, sentinels (`-999`, `NA`), or empty entries are parsed as `None` and never converted to zeros.
4. **Idempotency:** Re-running ingestion for the same station and valid timestamp creates 0 duplicates thanks to PostgreSQL `ON CONFLICT DO NOTHING`.

### 10.6 Scientific Limitations of Modeled Estimates
- **Grid Resolution vs Microscale Sensors:** Open-Meteo provides modeled chemical transport forecasts (derived from ECMWF Copernicus CAMS and atmospheric reanalysis) on a regional grid (~10–25 km). Ground CAAQMS stations measure localized, microscale street-canyon and emission-source air.
- **Topography and Local Sources:** Biomass burning, local trash fires, and vehicle idling at intersections (e.g. Anand Vihar bus terminal) cause localized ground concentration spikes not captured by regional gridded models.
- **Zero-Cost Budget Compliance:** Open-Meteo's Air Quality API is free for non-commercial open-source research and development, adhering strictly to the ₹0 project budget.
- **Attribution:** Data provided by [Open-Meteo](https://open-meteo.com/) under Creative Commons Attribution 4.0 International (CC BY 4.0), utilizing data from Copernicus Atmosphere Monitoring Service (CAMS).

---

## 11. Historical Data Collection & Forecasting Dataset Design (Phase 4 Step 1)

### 11.1 Historical Ingestion Pipeline
To train future forecasting models without relying on real-time polling, Vayu AI supports historical reanalysis ingestion via Open-Meteo:

```powershell
# From repository root:
.\.venv\Scripts\python -m backend.app.scripts.ingest_historical_aqi --source open_meteo --start 2026-09-01 --end 2026-09-07

# Or specify a subset of station IDs:
.\.venv\Scripts\python -m backend.app.scripts.ingest_historical_aqi --source open_meteo --start 2026-09-01 --end 2026-09-07 --stations anand-vihar,punjabi-bagh
```

**Key Pipeline Features:**
- **Automatic Request Chunking:** Date windows exceeding 30 days are automatically chunked into consecutive intervals and stitched seamlessly.
- **Transient Error Resilience:** Implements exponential backoff retries for network drops, timeouts, and HTTP 5xx errors.
- **Rate-Limit Throttling:** Detects HTTP 429 responses and throttles backoff delays.
- **Idempotent Persistence:** Duplicate records are rejected at the database layer using PostgreSQL `ON CONFLICT DO NOTHING` on `(station_id, provider, valid_time)`.

### 11.2 Historical CPCB Data Strategy & Limitations
- **OGD API Limitation:** The official Indian government portal (`data.gov.in` resource `3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69`) publishes real-time observation snapshots only and does not expose a free public historical REST query endpoint for past date windows.
- **Strategy:** Historical training sequences for development are populated using Copernicus CAMS reanalysis via Open-Meteo and strictly labeled as `provider='open-meteo'` in `modeled_air_quality_estimates`. Real-time ground truth observations continue to be ingested into `air_quality_readings` whenever the CPCB API is accessible. The system never fakes or synthesizes official CPCB historical observations.

### 11.3 Dataset Preparation & Quality Auditing
The dataset builder ([dataset_builder.py](file:///c:/Users/patra/OneDrive/Pictures/Desktop/vayu-ai/backend/app/services/dataset_builder.py)) extracts chronological station series and conducts rigorous quality validation:
- **Zero Imputation Policy:** Missing hours are flagged with `is_missing_hour=True` and left as `None`. Missing measurements are **never** silently zeroed or linearly interpolated.
- **Strict Provenance Isolation:** Datasets query either `open_meteo` or `cpcb` strictly; sources are never mixed into a single composite sequence.
- **Dataset Quality Diagnostic:** Computes total expected hours, available hours, missing hours, completeness percentage, duplicate timestamp checks, and field-level null counts.

```python
from datetime import datetime, timezone
from app.database import get_sessionmaker
from app.services.dataset_builder import build_hourly_dataset

db = get_sessionmaker()()
dataset = build_hourly_dataset(
    db=db,
    station_id="anand-vihar",
    start_time=datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc),
    end_time=datetime(2026, 9, 7, 23, 0, tzinfo=timezone.utc),
    source="open_meteo",
)
print(dataset.quality_report.summary())
```

### 11.4 Forecasting Dataset Design & Anti-Leakage Rules
Detailed specification available at [docs/forecasting_dataset_design.md](file:///c:/Users/patra/OneDrive/Pictures/Desktop/vayu-ai/docs/forecasting_dataset_design.md):
- **Forecast Horizons:** 24h, 48h, and 72h future prediction targets ($t_0 + 24$, $t_0 + 48$, $t_0 + 72$).
- **Lag Features:** Autoregressive lags at $t_0 - \{1, 2, 3, 6, 12, 24, 48, 72\}$ and co-pollutant lags at $t_0 - \{1, 6, 24\}$.
- **Rolling Statistics:** Backward-looking rolling mean, min, max, std over 6h, 12h, and 24h past windows.
- **Diurnal/Cyclical Encodings:** $\sin$ and $\cos$ encodings for hour-of-day and month-of-year.
- **Zero Look-Ahead Leakage:** Target variables are strictly segregated from feature dictionaries.
- **Temporal Embargo Splits:** Chronological train/val/test splits enforce a 72-hour embargo gap to prevent training target horizons from overlapping with evaluation features.

---

## 12. Baseline Forecasting Engine (Phase 4 Step 2)

### 12.1 Objective & Scope
Phase 4 Step 2 implements and rigorously evaluates three foundational baseline models for forecasting $\text{PM}_{2.5}$ mass concentrations at $+24\text{h}$, $+48\text{h}$, and $+72\text{h}$ horizons across all six Delhi NCR stations.

> [!NOTE]
> **Production Safety:** The baseline models are developed in isolated modules ([baselines.py](file:///c:/Users/patra/OneDrive/Pictures/Desktop/vayu-ai/backend/app/services/baselines.py)). The existing synthetic 72-hour forecast API (`/api/forecast`) and frontend remain completely unchanged and fully operational.

### 12.2 Model Definitions

1. **Model A: Persistence Baseline**
   - Assumes pollutant concentrations remain static over the forecast horizon.
   - Prediction rule: $\hat{y}(t_0 + h) = y(t_0)$ (uses the latest available $\text{PM}_{2.5}$ observation at prediction time $t_0$).

2. **Model B1: Seasonal Naive Baseline (Historical $t_0 - 24\text{h}$)**
   - Predicts based on the diurnal cycle from the previous day at the same hour relative to reference time $t_0$.
   - Prediction rule: $\hat{y}(t_0 + h) = y(t_0 - 24\text{h})$.
   - Captures daily atmospheric boundary layer expansion and nocturnal particulate trapping patterns.

3. **Model B2: Horizon-Aligned Daily Seasonal Baseline**
   - Predicts using the latest available observation at or before prediction time $t_0$ that shares the exact same hour-of-day as the forecast target ($t_0 + h$).
   - Prediction rule: $\hat{y}(t_0 + h) = y(t_0 - \text{lag})$ where $\text{lag} = (24 - (h \pmod{24})) \pmod{24}$.
   - For daily multiples ($h \in \{24, 48, 72\}$): $\text{lag} = 0$, so $\hat{y}(t_0 + h) = y(t_0)$, aligning with the latest available observation ($t_0$).

4. **Model C: Ridge Regression Baseline**
   - Trains separate horizon-specific L2-regularized linear models for $+24\text{h}$, $+48\text{h}$, and $+72\text{h}$.
   - **Feature Vector (44 Causal Features):**
     - Target autoregressive lags: $t_0 - \{1, 2, 3, 6, 12, 24, 48, 72\}\text{h}$ and $t_0$ current.
     - Co-pollutant lags ($\text{PM}_{10}, \text{NO}_2, \text{SO}_2, \text{CO}, \text{O}_3$): $t_0$ and $t_0 - \{1, 6, 24\}\text{h}$.
     - Backward rolling statistics over past 6h, 12h, and 24h windows (mean, min, max, std).
     - Cyclical calendar encodings ($\sin/\cos$ for hour of day, day of week, weekend flag, $\sin/\cos$ for month).
   - **Preprocessing Pipeline:**
     - `SimpleImputer(strategy="median")` handles any missing co-pollutants.
     - `StandardScaler()` normalizes lag and rolling features.
     - **Leakage Protection:** Preprocessing and scaling are fitted **strictly on the training partition**. Validation and test partitions are transformed without re-fitting.

### 12.3 Chronological Evaluation & Model Selection Methodology

- **Historical Dataset:** 90-day Open-Meteo modeled/reanalysis dataset (`2024-10-01 00:00:00 UTC` to `2024-12-29 23:00:00 UTC`), containing 2,160 hourly records per station (12,960 total records).
- **Usable Supervised Samples:** 2,088 samples per station (first 72 hours form the initial lag history; samples anchored from `2024-10-04 00:00:00 UTC`).
- **Chronological Partitions:**
  - **Train:** 1,461 samples (~70%, covering `2024-10-04` to `2024-12-03`).
  - **Validation:** 241 samples (~15%, covering `2024-12-06` to `2024-12-16`).
  - **Test:** 242 raw samples (~15%, covering `2024-12-19` to `2024-12-29`).
- **Horizon-Aware Temporal Embargo:** A 72-hour embargo buffer is enforced between train and validation, and between validation and test. This ensures that the $+72\text{h}$ targets of training samples do not overlap with feature steps in the evaluation set.
- **Strict Model Selection Principle:**
  - Hyperparameter tuning ($\alpha$) and model selection decisions are made **strictly on the Validation partition** (lowest Validation MAE).
  - The held-out **Test partition is never used to select hyperparameters or choose a deployed model**, guaranteeing zero test-set data snooping.
- **Missing Target Exclusion:** Samples near the end of the test window where future targets extend beyond `2024-12-29 23:00` are strictly excluded from horizon evaluation (Test $N = 218$ for $+24\text{h}$, $N = 194$ for $+48\text{h}$, $N = 170$ for $+72\text{h}$). Missing targets are **never silently imputed**.

### 12.4 Running Baseline Training & Evaluation CLI

Execute the training runner across a single station or all six stations:

```powershell
# Run baseline evaluation for a specific station:
.\.venv\Scripts\python -m backend.app.scripts.train_baselines --station anand-vihar --pollutant pm2_5

# Run baseline evaluation across ALL six Delhi NCR stations and export metrics:
.\.venv\Scripts\python -m backend.app.scripts.train_baselines --station all --pollutant pm2_5 --export-csv artifacts/models/baseline_evaluation_metrics.csv --export-json artifacts/models/baseline_evaluation_metrics.json
```

### 12.5 Model Artifact Management

Model weights and audit metadata are automatically saved locally under the git-ignored `artifacts/models/` directory:
- **Trained Pipeline:** Saved via `joblib` as `artifacts/models/{station_id}/pm2_5_h{horizon}/model.joblib`.
- **Audit Metadata:** Stored as `metadata.json`, capturing station ID, target pollutant, forecast horizon, exact feature column ordering (44 features), hyperparameters ($\alpha$), sample counts, training date range, train/val/test metrics, timestamp, and data provenance disclaimers.
- **Anti-Leakage Guarantee:** Stored metadata records `model_selection: {"decision_partition": "validation", "selected_model": ...}` and excludes test-set-derived selection decisions.

### 12.6 Evaluation Results & Metrics (Audit Verified)

All metrics evaluated on the held-out test partition (`2024-12-19` to `2024-12-29 UTC`):

| Station | Horizon | Model | Test $N$ | MAE ($\mu\text{g/m}^3$) | RMSE ($\mu\text{g/m}^3$) | $R^2$ | Validation Selection |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Anand Vihar** | +24h | Persistence | 218 | 39.23 | 48.70 | -0.435 | |
| | +24h | Seasonal Naive ($t_0-24\text{h}$) | 218 | 44.72 | 56.11 | -0.906 | |
| | +24h | Seasonal (Horizon-Aligned) | 218 | 39.23 | 48.70 | -0.435 | |
| | +24h | **Ridge ($\alpha=100$)** | 218 | **34.52** | **45.25** | **-0.239** | **Selected on Val** |
| | +48h | Persistence | 194 | 45.12 | 55.74 | -0.953 | |
| | +48h | Seasonal Naive ($t_0-24\text{h}$) | 194 | 37.97 | 51.22 | -0.649 | |
| | +48h | Seasonal (Horizon-Aligned) | 194 | 45.12 | 55.74 | -0.953 | |
| | +48h | **Ridge ($\alpha=500$)** | 194 | **33.47** | **42.26** | **-0.122** | **Selected on Val** |
| | +72h | **Persistence / Aligned** | 170 | 40.98 | 54.11 | -1.403 | **Selected on Val** |
| | +72h | Seasonal Naive ($t_0-24\text{h}$) | 170 | 31.63 | 42.09 | -0.453 | |
| | +72h | Ridge ($\alpha=1000$) | 170 | 29.68 | 37.63 | -0.162 | |
| **Punjabi Bagh** | +24h | **Persistence / Aligned** | 218 | 39.23 | 48.70 | -0.435 | **Selected on Val** |
| | +24h | Seasonal Naive ($t_0-24\text{h}$) | 218 | 44.72 | 56.11 | -0.906 | |
| | +24h | Ridge ($\alpha=100$) | 218 | 34.20 | 44.79 | -0.214 | |
| | +48h | **Ridge ($\alpha=500$)** | 194 | **33.62** | **41.69** | **-0.092** | **Selected on Val** |
| | +72h | **Persistence / Aligned** | 170 | 40.98 | 54.11 | -1.403 | **Selected on Val** |
| | +72h | Ridge ($\alpha=1000$) | 170 | 29.21 | 36.78 | -0.110 | |
| **Mandir Marg** | +24h | **Persistence / Aligned** | 218 | 39.23 | 48.70 | -0.435 | **Selected on Val** |
| | +24h | Ridge ($\alpha=100$) | 218 | 34.42 | 45.08 | -0.230 | |
| | +48h | **Ridge ($\alpha=500$)** | 194 | **33.53** | **42.28** | **-0.123** | **Selected on Val** |
| | +72h | **Persistence / Aligned** | 170 | 40.98 | 54.11 | -1.403 | **Selected on Val** |
| | +72h | Ridge ($\alpha=1000$) | 170 | 29.73 | 37.56 | -0.157 | |
| **IGI Airport (T3)**| +24h | **Persistence / Aligned** | 218 | 36.02 | 46.66 | -0.266 | **Selected on Val** |
| | +24h | Ridge ($\alpha=1000$) | 218 | 30.20 | 38.58 | 0.134 | |
| | +48h | **Ridge ($\alpha=100$)** | 194 | 43.89 | 56.42 | -1.008 | **Selected on Val** |
| | +48h | Seasonal Naive ($t_0-24\text{h}$) | 194 | 40.37 | 51.29 | -0.660 | *(Best on Test)* |
| | +72h | **Ridge ($\alpha=500$)** | 170 | **31.85** | **40.26** | **-0.342** | **Selected on Val** |
| **R.K. Puram** | +24h | **Persistence / Aligned** | 218 | 36.02 | 46.66 | -0.266 | **Selected on Val** |
| | +24h | Ridge ($\alpha=1000$) | 218 | 30.35 | 38.78 | 0.125 | |
| | +48h | **Ridge ($\alpha=100$)** | 194 | 43.35 | 56.19 | -0.992 | **Selected on Val** |
| | +48h | Seasonal Naive ($t_0-24\text{h}$) | 194 | 40.37 | 51.29 | -0.660 | *(Best on Test)* |
| | +72h | **Ridge ($\alpha=500$)** | 170 | **31.57** | **40.11** | **-0.332** | **Selected on Val** |
| **Noida Sec 62** | +24h | **Ridge ($\alpha=100$)** | 218 | **34.74** | **45.42** | **-0.249** | **Selected on Val** |
| | +48h | **Ridge ($\alpha=500$)** | 194 | **33.46** | **42.08** | **-0.112** | **Selected on Val** |
| | +72h | **Persistence / Aligned** | 170 | 40.98 | 54.11 | -1.403 | **Selected on Val** |
| | +72h | Ridge ($\alpha=1000$) | 170 | 29.19 | 37.04 | -0.126 | |

### 12.7 Audit Findings on Identical Station Metrics

During the Phase 4 Step 2.5 independent evaluation audit:
1. **Grid Resolution Clustering:** Open-Meteo Air Quality utilizes Copernicus Atmosphere Monitoring Service (CAMS) global reanalysis at ~0.4° horizontal resolution (~40 km).
   - The northern cluster (Anand Vihar, Punjabi Bagh, Mandir Marg, Noida Sec 62) falls within the exact same northern grid box, producing identical PM2.5, PM10, NO2, SO2, and O3 sequences in the historical 2024 reanalysis.
   - The southern cluster (IGI Airport T3, RK Puram) falls within the southern grid box, producing an identical aerosol sequence to each other, but differing significantly from the northern cluster (up to 75 $\mu\text{g/m}^3$ PM2.5 difference).
2. **Co-Pollutant Terrain Differentiation:** Carbon monoxide (CO) values differ between stations due to local elevation modeling (208m to 236m), yielding unique 44-feature representations for Ridge training.
3. **No Code/Data Mixing Bug:** Station coordinates and database queries were confirmed 100% distinct. The identical baseline metrics are an authentic consequence of gridded reanalysis resolution over urban domains.

---

## 13. Phase 4 Step 3: Experimental ML Forecast API

Phase 4 Step 3 exposes the evaluated baseline forecasting models (+24h, +48h, +72h) through a dedicated, isolated FastAPI endpoint without altering the frontend or operational synthetic endpoints.

### 13.1 Endpoint Specification

```http
GET /api/forecast/experimental?station_id=anand-vihar[&reference_time=2024-12-15T12:00:00Z][&max_staleness_hours=24]
```

#### Query Parameters:
| Parameter | Type | Required | Default | Description |
| :--- | :--- | :---: | :---: | :--- |
| `station_id` | `string` | **Yes** | — | Supported Delhi NCR station identifier (e.g. `anand-vihar`, `igi-airport-t3`). |
| `reference_time` | `datetime (ISO-8601)` | No | `None` | Point-in-time UTC forecast anchor $t_0$. If omitted, uses current time and enforces real-time freshness. |
| `max_staleness_hours` | `integer` | No | `24` | Maximum allowable age of the latest modeled record relative to clock time (1–8760 hours). |

### 13.2 Response Schema

The endpoint responds with typed `ExperimentalForecastResponse`:
```json
{
  "status": "experimental",
  "is_experimental": true,
  "station_id": "anand-vihar",
  "station_name": "Anand Vihar",
  "prediction_time_utc": "2024-12-15T12:00:00Z",
  "target_pollutant": "pm2_5",
  "units": "µg/m³",
  "data_provider": "Open-Meteo (Copernicus CAMS modeled/reanalysis)",
  "training_period": {
    "start_utc": "2024-10-01T00:00:00Z",
    "end_utc": "2024-12-29T23:00:00Z"
  },
  "disclaimer": "Experimental ML baseline forecast derived from Open-Meteo Copernicus CAMS atmospheric reanalysis data. These are NOT official CPCB ground observations and do NOT replace operational forecasts.",
  "horizons": [
    {
      "horizon_hours": 24,
      "horizon_label": "+24h",
      "target_time_utc": "2024-12-16T12:00:00Z",
      "predicted_pm2_5": 86.02,
      "selected_model": "ridge",
      "model_type": "RidgeRegression(alpha=100.0)",
      "artifact_id": "anand-vihar_pm2_5_h24_ridge",
      "validation_mae": 33.323
    },
    {
      "horizon_hours": 48,
      "horizon_label": "+48h",
      "target_time_utc": "2024-12-17T12:00:00Z",
      "predicted_pm2_5": 78.67,
      "selected_model": "ridge",
      "model_type": "RidgeRegression(alpha=500.0)",
      "artifact_id": "anand-vihar_pm2_5_h48_ridge",
      "validation_mae": 39.546
    },
    {
      "horizon_hours": 72,
      "horizon_label": "+72h",
      "target_time_utc": "2024-12-18T12:00:00Z",
      "predicted_pm2_5": 129.0,
      "selected_model": "persistence",
      "model_type": "Persistence Baseline (y_hat = y(t_0))",
      "artifact_id": "anand-vihar_pm2_5_h72_persistence",
      "validation_mae": 50.385
    }
  ]
}
```

### 13.3 Integrity, Freshness, & Anti-Leakage Safeguards

1. **Anti-Leakage Guarantee:** Point-in-time inference strictly queries $t \le t_0$. No future observations ($t > t_0$) are ever accessed or leaked into the 44-element feature vector.
2. **Validation-Based Dispatch:** Models are dispatched strictly based on decisions made on the validation partition (e.g. Ridge for Anand Vihar +24h/+48h, Persistence for +72h). Test-set metrics are strictly held out.
3. **Continuous 72-Hour History Requirement:** Generating the 44 autoregressive, co-pollutant, and rolling features requires a continuous 73-point timeline $[t_0 - 72\text{h}, t_0]$. If any required lag (1, 2, 3, 6, 12, 24, 48, 72h) is missing, the endpoint raises HTTP 503 `InsufficientHistoryError`.
4. **Stale Historical Data Rejection:** Models were trained on October–December 2024 reanalysis data. The API strictly rejects presenting stale 2024 data as live 2026 forecasts (`StaleDataError`, HTTP 503).
5. **Nonnegative Clamping:** All predictions are clamped to $\max(0.0, \hat{y})$ to guarantee physically plausible PM2.5 concentrations.
6. **Safe Artifact Loading:** Artifact paths are strictly resolved within `artifacts/models/` against validated station identifiers, preventing path traversal attacks.

### 13.4 Known Limitations

- **Gridded Resolution:** Uses 0.4° (~40 km) Copernicus CAMS gridded reanalysis, which does not resolve microscale hyper-local street canopy variations.
- **Linear Baselines Only:** Phase 4 Step 3 strictly serves linear Ridge and naive baselines; nonlinear temporal architectures (e.g., LSTM, Temporal Fusion Transformers) are reserved for future phases.
- **Data Provenance:** Predictions are derived from Open-Meteo numerical models and are **not** certified CPCB ground monitoring station observations.

---

## 14. Phase 4 Step 4: Live Forecast Data Readiness

Phase 4 Step 4 resolves the live data freshness prerequisite by backfilling the most recent 7 completed days of Open-Meteo numerical estimates, enabling legitimate real-time inference without fabricating synthetic data.

### 14.1 Recent-History Ingestion Runner

The historical ingestion CLI supports `--recent-days` and automatic future-timestamp exclusion:

```powershell
# Ingest the last 7 completed days for all six Delhi NCR stations (excluding future hours):
.\.venv\Scripts\python -m backend.app.scripts.ingest_historical_aqi --recent-days 7

# Ingest with an explicit UTC cutoff timestamp:
.\.venv\Scripts\python -m backend.app.scripts.ingest_historical_aqi --recent-days 7 --cutoff-utc 2026-10-08T08:00:00Z
```

#### Safeguards Enforced:
1. **UTC-Aware Boundaries:** All incoming timestamps are parsed as UTC and truncated to the start of the hour (`minute=0, second=0`).
2. **Strict Future Exclusion:** Any modeled forecast values beyond current time ($t > \text{now\_utc}$) are discarded prior to database persistence.
3. **Idempotent Inserts:** Uses PostgreSQL `ON CONFLICT (station_id, provider, valid_time) DO NOTHING` on `uq_modeled_estimate_station_provider_time` to prevent duplicate rows.
4. **CPCB Isolation:** Official observations in `air_quality_readings` are completely separate and unaffected.
5. **₹0 Budget:** Relies exclusively on Open-Meteo's free non-commercial air-quality reanalysis API.

### 14.2 Station-by-Station Readiness Verification

All six monitoring stations possess complete 72-hour lag windows ($N=73$ consecutive hourly records) and pass live inference:

| Station ID | Station Name | Continuous 72h Window | Future Records ($t > \text{now}$) | Duplicate Records | Real-Time Endpoint Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `anand-vihar` | Anand Vihar | **73 / 73** (0 gaps) | 0 | 0 | **HTTP 200 OK** |
| `punjabi-bagh` | Punjabi Bagh | **73 / 73** (0 gaps) | 0 | 0 | **HTTP 200 OK** |
| `mandir-marg` | Mandir Marg | **73 / 73** (0 gaps) | 0 | 0 | **HTTP 200 OK** |
| `igi-airport-t3` | IGI Airport T3 | **73 / 73** (0 gaps) | 0 | 0 | **HTTP 200 OK** |
| `rk-puram` | R.K. Puram | **73 / 73** (0 gaps) | 0 | 0 | **HTTP 200 OK** |
| `noida-sec62` | Sector 62, Noida | **73 / 73** (0 gaps) | 0 | 0 | **HTTP 200 OK** |

### 14.3 Optional Scheduled Ingestion Design (Windows Task Scheduler)

To maintain an uninterrupted 72-hour history without manual execution, an optional hourly task can be scheduled via PowerShell:

```powershell
# Definition of optional hourly refresh task:
$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -Command 'cd C:\Users\patra\OneDrive\Pictures\Desktop\vayu-ai; .\.venv\Scripts\python.exe -m backend.app.scripts.ingest_historical_aqi --recent-days 3'"

$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1)

$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Register task (Requires user authorization; do not register without approval):
# Register-ScheduledTask -TaskName "VayuAI_OpenMeteo_HourlyIngest" -Action $Action -Trigger $Trigger -Settings $Settings
```

- **Architecture:** Local execution only, ₹0 additional infrastructure.
- **Rollback / Unregister:** `Unregister-ScheduledTask -TaskName "VayuAI_OpenMeteo_HourlyIngest" -Confirm:$false`.

---

## 15. Phase 4 Step 5: Model Reliability and Backend Hardening

Phase 4 Step 5 completes the scientific validation and production-readiness hardening of the baseline forecasting backend, verifying interval semantics, model generalization across disjoint time periods, explicit contract boundaries, and zero-cost deployment prerequisites.

### 15.1 Hourly Data Semantics & Interval Completion

- **Open-Meteo Timestamp Convention:** In the Open-Meteo Air Quality API, each hourly timestamp $t$ represents the *beginning* of the 1-hour interval $[t, t+1\text{h})$.
- **Completion Invariant:** An hourly interval is incomplete until wall-clock time $T \ge t + 1\text{h}$.
- **Invariant Enforcement:** Ingestion and live forecast inference now strictly enforce $t \le \text{truncate\_to\_hour}(T) - 1\text{h}$ when referencing completed observations. An incomplete, in-progress interval (e.g. 10:00 UTC at 10:25 UTC) is never mislabeled as a completed observation and is never selected as the live inference anchor $t_0$.

### 15.2 Data Product Provenance & Disclaimers

The system strictly differentiates underlying atmospheric modeling products:
1. **CAMS Global Reanalysis (Historical Training):** Used for historical training and validation (October 1 – December 29, 2024). Produced with a 2–5 day publication lag using atmospheric data assimilation and retrospective numerical analysis.
2. **CAMS Global Numerical Forecast (Live Inference):** Used for real-time and recent-window backfills (October 2026). Generated via daily numerical forecast cycles by the Copernicus Atmosphere Monitoring Service.
3. **CPCB Isolation:** Modeled estimates are stored in `modeled_air_quality_estimates` and never mixed with ground-station observations in `air_quality_readings`.

### 15.3 Out-of-Time Model Generalization Evaluation (Held-Out October 2026)

To test generalization under strictly out-of-time conditions, models trained on winter 2024 (Oct–Dec 2024) were evaluated against the held-out October 1–8, 2026 period ($N=82$ for +24h, $N=58$ for +48h, $N=34$ for +72h) with zero re-training or tuning.

> [!NOTE]
> **Model Selection Protocol:** All model serving decisions are anchored strictly to the 2024 validation partition (`lowest_validation_mae`). In accordance with rigorous scientific practices, model selection decisions are **never** retroactively altered based on held-out test or out-of-time evaluation results.

| Station | Horizon | Validation-Selected (Served) Model | Served Model Out-of-Time MAE | Ridge Out-of-Time MAE | Persistence Out-of-Time MAE | Seasonal-24h Out-of-Time MAE |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **IGI Airport T3** | +24h | **Persistence** | **16.58 µg/m³** | 14.47 µg/m³ | 16.58 µg/m³ | 17.50 µg/m³ |
| **R.K. Puram** | +24h | **Persistence** | **16.73 µg/m³** | 14.49 µg/m³ | 16.73 µg/m³ | 17.96 µg/m³ |
| **Anand Vihar** | +24h | **Ridge** | **21.18 µg/m³** | 21.18 µg/m³ | 20.80 µg/m³ | 22.29 µg/m³ |
| **Sector 62 Noida**| +24h | **Ridge** | **21.17 µg/m³** | 21.17 µg/m³ | 20.78 µg/m³ | 22.05 µg/m³ |
| **Mandir Marg** | +24h | **Persistence** | **20.84 µg/m³** | 21.15 µg/m³ | 20.84 µg/m³ | 22.12 µg/m³ |
| **Punjabi Bagh** | +24h | **Persistence** | **20.85 µg/m³** | 21.39 µg/m³ | 20.85 µg/m³ | 22.12 µg/m³ |
| **All Stations** | +48h | **Ridge** | **28.34–37.65 µg/m³** | 28.34–37.65 µg/m³ | 19.44–23.74 µg/m³ | 22.32–22.98 µg/m³ |
| **All Stations** | +72h | **Persistence** | **18.72–20.40 µg/m³** | 20.73–26.26 µg/m³ | 18.72–20.40 µg/m³ | 15.06–25.25 µg/m³ |

#### Scientific Insights:
- **At +24h (IGI Airport & R.K. Puram):** The served baseline is Persistence (selected on 2024 validation data where Persistence MAE of 35.85 µg/m³ outperformed Ridge at 36.88 µg/m³). The out-of-time evaluation shows that the linear Ridge model generalized well to the October 2026 conditions (14.47–14.49 µg/m³ vs Persistence at 16.58–16.73 µg/m³). However, preserving integrity means keeping the pre-registered validation selection intact.
- **At +48h:** Ridge was chosen by validation data, but on the October 2026 period, Persistence yielded lower MAE (19.4–23.7 µg/m³ vs Ridge at 28.3–37.7 µg/m³), confirming that linear autoregressive models face limits beyond 24 hours.
- **At +72h:** Persistence was correctly identified by validation data as the superior baseline and generalized solidly (18.7–20.4 µg/m³ MAE).
- **Meteorological Context:** Absolute errors across all methods in October 2026 are lower than peak winter December 2024 (where baseline MAEs ranged 33–50 µg/m³), reflecting calmer pre-winter atmospheric stability.

### 15.4 Forecast Output Contracts: Discrete Milestones

The experimental endpoint (`GET /api/forecast/experimental`) explicitly specifies its horizon structure:
- **`forecast_structure`:** `"discrete_milestones_24h_48h_72h"`
- **`hourly_sequence_note`:** *"Baseline models predict 3 discrete horizons (+24h, +48h, +72h). A full 72-step hourly series requires direct 72-head multi-output models or recursive neural autoregression."*
- **`data_product`:** `"CAMS Global Operational Forecast (live inference) & CAMS Global Reanalysis (training)"`

### 15.5 Requirements for a Full 72-Step Hourly Forecast (Phase 5 Roadmap)

Serving a genuine, continuous 72-step hourly sequence requires the following architectural components:
1. **Direct Multi-Output Heads:** 72 discrete estimators $f_1, f_2, \dots, f_{72}$ or a multi-output regressor yielding $\hat{y} \in \mathbb{R}^{72}$.
2. **Recursive Autoregression or Sequence Models:** A recurrent neural architecture (e.g. GRU, LSTM, or Temporal Fusion Transformer) predicting iteratively $\hat{y}_{t+k} = f(\hat{y}_{t+k-1}, \dots)$.
3. **NWP Future Exogenous Forcing:** Ingestion of future meteorological forecasts (boundary layer height, wind speed, temperature) at lead hours $h \in [1, 72]$.

### 15.6 Deployment Readiness & ₹0 Development Budget Verification

- **Cost:** ₹0. All components operate locally with free open-source tooling (PostgreSQL, FastAPI, Vite, Open-Meteo non-commercial tier).
- **Environment Discovery:** Automatic traversal across parent directories (`.env`).
- **Health Checks:** `/api/health` and `/api/health/db` report active PostgreSQL connectivity and Phase 4 status.
- **Test Suite:** 121 automated backend tests passing; frontend TypeScript build passing with zero errors.







