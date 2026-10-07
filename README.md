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

## 10. Official CPCB Air Quality Ingestion Pipeline (Phase 3 Step 3)

### Primary Data Source
- **Platform:** Open Government Data (OGD) Platform India ([data.gov.in](https://data.gov.in))
- **Dataset:** *Real time Air Quality Index from various locations*
- **Contributor:** Central Pollution Control Board (CPCB) / Ministry of Environment, Forest and Climate Change (MoEFCC)
- **Official Resource ID:** `3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69`

### Environment Configuration
Register for a free account at [data.gov.in](https://data.gov.in), generate an API token, and add it to your `.env`:
```ini
DATA_GOV_IN_API_KEY=your_api_key_here
DATA_GOV_IN_RESOURCE_ID=3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69
```

### Running Ingestion Locally
Execute the manual ingestion runner from the repository root:
```powershell
.\.venv\Scripts\Activate.ps1
python -m backend.app.scripts.ingest_aqi
```
Or from the `backend/` directory:
```bash
python -m app.scripts.ingest_aqi
```

Output:
```text
=== Vayu AI: CPCB AQI Data Ingestion ===
Fetched records: X
Normalized observations: Y
Stations inserted/updated: Z
Readings inserted: N
Duplicates skipped: M
========================================
```

### Ingestion Architecture & Data Integrity
1. **Multi-Record Normalization:** data.gov.in publishes each pollutant measurement as a separate entry. The ingestion engine groups records by `(station, timestamp)` into a unified observation containing `pm2_5`, `pm10`, `no2`, `so2`, `co`, `o3`, and `aqi` where present.
2. **Deterministic Station Matching:** Official station strings (e.g., `Anand Vihar, Delhi - DPCC`) are matched against Vayu AI's curated station directory (`anand-vihar`), preserving canonical station IDs and geospatial coordinates.
3. **Idempotency & Duplicate Protection:** Enforces the database unique constraint `uq_station_reading_timestamp` on `(station_id, timestamp)` via PostgreSQL `ON CONFLICT DO NOTHING`. Running ingestion multiple times against identical observation timestamps produces zero duplicate rows.
4. **Instrument Error Sanitization:** CPCB and OGD note that continuous real-time CAAQMS sensors occasionally transmit error codes (`-999`, `NA`, `null`). The parser converts invalid codes into null values and never converts missing readings into zeros.
5. **Architectural Separation:** Live ground observations persist strictly in `air_quality_readings`. The 72-hour synthetic demo forecast remains separate and uncompromised for Phase 2 UI contracts.


