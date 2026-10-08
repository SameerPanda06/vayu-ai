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



