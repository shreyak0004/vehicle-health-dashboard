# VehicleGPT — Intelligent On-Device Vehicle Health & Diagnostics Assistant

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/framework-Flask-black.svg)](https://flask.palletsprojects.com/)
[![Tests](https://img.shields.io/badge/tests-62%20passed%20(100%25)-brightgreen.svg)](https://docs.pytest.org/)
[![Model](https://img.shields.io/badge/model-Qwen2.5--0.5B--Instruct%20(GGUF)-orange.svg)](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF)

An offline, on-device natural-language vehicle health and diagnostics assistant for automotive cockpits and service engineers. VehicleGPT bridges automotive bus telemetry with an edge Small Language Model (SLM), providing factual, conversational diagnostic intelligence without cloud dependency.

---

## 🚀 Key Features

- **⚡ Deterministic Grounded Analytics**: Zero hallucination guarantee. Computes exact averages, energy consumption ($Wh/km$), battery state-of-charge ($SOC$), and mode comparisons via deterministic SQL before language model synthesis.
- **🛡️ ISO 26262 Read-Only Safety Perimeter**: Strictly blocks vehicle control or actuation commands (e.g., *"turn off headlights"*) and explicitly reports unmonitored signals (e.g., tyre pressure) rather than fabricating answers.
- **🔌 Unified Telemetry Ingestion**: Common internal schema accepting simulated scenario streams and pre-recorded trips now, with plug-and-play adapter interfaces for vehicle buses.
- **🧠 Offline Edge SLM**: Runs locally via `llama-cpp-python` with **Qwen2.5-0.5B-Instruct** (4-bit GGUF) on 2 CPU threads within a ~560 MB RAM footprint (well under the 2 GB embedded budget).
- **🎨 Modern Luxury Cockpit UI**: Features a sleek obsidian vehicle silhouette in both light and dark themes, dynamic vector lines connecting telemetry cards directly to vehicle sensor hotspots, and a single-toggle collapsible layout.

---

## 🏛️ Architecture & Data Flow

```
+--------------------------------------------------------------------------------------------------+
|                                    VEHICLE DATA SOURCES                                          |
|                                                                                                  |
|   [Active Simulated Inputs]                      [Planned Hardware Inputs (Adapter Ready)]       |
|   - Real-time Scenario Simulator                 - Physical CAN / CAN-FD Bus Transceiver         |
|   - Recorded Trip CSV Replay                     - SOME/IP Ethernet Services                     |
|                                                  - Android Automotive VHAL (AIDL)                |
|                                                  - QNX Syslog & Diagnostic UDS Dongle            |
+-----------------------------------+--------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------------------------------+
|                                 SOURCE-SPECIFIC ADAPTERS                                         |
|  ingestion/adapters/ (CAN, SOME/IP, VHAL, QNX, ADAS, Camera, Diagnostics)                       |
+-----------------------------------+--------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------------------------------+
|                          NORMALIZATION & VALIDATION ENGINE                                       |
|  - Range bounds checking, unit normalization, and provenance tracking                            |
|  - Common Schema: NormalizedTelemetry, NormalizedEvent                                          |
+-----------------------------------+--------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------------------------------+
|                            SQLITE STORAGE (Read-Write Ingestion)                                 |
|  vehicle_readings (timestamp, speed, battery_temp, soc, energy, mode, odo, ambient, range)        |
|  vehicle_events (timestamp, event_type, severity, description)                                   |
+-----------------------------------+--------------------------------------------------------------+
                                    |
                                    v (Read-Only Connection for Safety)
+--------------------------------------------------------------------------------------------------+
|                        DETERMINISTIC RETRIEVAL & SAFETY ENGINE                                    |
|  1. Time Range Parsing (relative & absolute dates)                                               |
|  2. Safety Refusal Guard (blocks actuation commands)                                             |
|  3. Unsupported Signal Guard (handles missing signals like tyre pressure without hallucinating)  |
|  4. Authoritative SQL Analytics (extremes, averages, trends, comparisons, ramps)                 |
+-----------------------------------+--------------------------------------------------------------+
                                    |
          +-------------------------+-------------------------+
          | (Supported & Safe)                                | (Unsupported or Guard Refusal)
          v                                                   v
+------------------------------------+              +------------------------------------+
|     LOCAL OFFLINE SLM              |              |       DIRECT DETERMINISTIC         |
|  Qwen2.5-0.5B-Instruct GGUF        |              |             FALLBACK               |
|  (llama.cpp, 2 threads, 491 MB)    |              |  - Instant response (< 2 ms)       |
|  Strict grounding in SQL evidence  |              |  - Zero hallucination guarantee    |
+-----------------+------------------+              +-----------------+------------------+
                  |                                                   |
                  +-------------------------+-------------------------+
                                            |
                                            v
+--------------------------------------------------------------------------------------------------+
|                          CHARCOAL & COPPER DASHBOARD & CHATBOT                                    |
|  - Dynamic SVG vectors tracking vehicle component hotspots across screen sizes                   |
|  - Single unified panel minimize toggle & responsive telemetry grid                              |
|  - Persistent Light & Dark Theme switching (localStorage)                                        |
+--------------------------------------------------------------------------------------------------+
```

---

## 💻 Tech Stack

- **Backend**: Python 3.10+, Flask, SQLite
- **Edge AI**: `llama-cpp-python`, Qwen2.5-0.5B-Instruct (`q4_k_m` GGUF, 491 MB)
- **Frontend**: Vanilla JavaScript, Chart.js, CSS3 (Charcoal & Copper design system, SVG vectors)
- **Testing & Verification**: Pytest, automated edge performance benchmarks

---

## 🛠️ Installation and Run Steps

### 1. Clone Repository & Install Dependencies
```bash
git clone https://github.com/shreyak0004/vehicle-health-dashboard.git
cd vehicle-health-dashboard
pip install -r requirements.txt
```

### 2. Download Offline Model Weights (Optional)
*The system includes instant deterministic fallback if no model is present. To enable local SLM synthesis:*
```bash
# Windows PowerShell
Invoke-WebRequest -Uri "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf" -OutFile "models/qwen2.5-0.5b-instruct-q4_k_m.gguf"

# Linux / macOS
curl -L -o models/qwen2.5-0.5b-instruct-q4_k_m.gguf https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf
```

### 3. Run Application
```bash
python app.py
```
Open **`http://127.0.0.1:5000`** in your browser.

---

## 💬 Sample Queries (Verified Working Examples)

| User Query | Engine Handling | Verified Grounded Output |
| :--- | :--- | :--- |
| **"Compare city vs highway energy consumption"** | `analytics.queries.compare_city_vs_highway` | Computes exact average speeds ($km/h$), energy efficiency ($Wh/km$), battery temperature differences, and timeframe compared. |
| **"What was the highest battery temperature yesterday?"** | `retrieval.query_engine.execute_query` | Returns exact peak recorded temperature (e.g. $48.2^\circ C$) with exact timestamp. |
| **"What is my current tyre pressure?"** | `Unsupported Signal Guard` | *"Tyre pressure data is not currently monitored by the connected vehicle telemetry bus."* (Refuses to guess). |
| **"Turn off headlights"** | `Safety Guard (ISO 26262)` | *"Refusal: VehicleGPT operates strictly in read-only diagnostic mode. Vehicle control commands cannot be executed."* |
| **"Why did the battery overheat yesterday?"** | `retrieval.query_engine.investigate_event` | Identifies thermal spike timestamp, correlated high-discharge draw, and applies temporal root-cause disclaimer. |

---

## 🧪 Tests and Benchmarks (Actual Measured Results)

### Test Suite
```bash
pytest -v
```
- **Results:** **62 / 62 passed (100%)** in 1.45s across unit, scenario, and routing tests.

### Measured Edge Performance (Dual-Core Embedded Profile)
- **Active Memory (RSS):** **561 MB** (Target: $< 2048\text{ MB}$, **72.6% safety headroom**).
- **Model Size on Disk:** **491 MB** (4-bit quantization).
- **Deterministic SQL Retrieval:** **2.4 ms** average response time.
- **Local SLM Generation:** **1.4 s** average latency on 2 CPU threads.

---

## ⚠️ Limitations & Future Work

### Current Limitations
- **Simulated Bus Telemetry**: Current telemetry stream is provided by the scenario simulator and recorded CSV files; physical CAN transceivers and Ethernet interfaces are modeled through adapter abstractions.
- **Signal Scope**: Unmonitored signals (such as individual tire pressures and high-resolution motor inverter RPM) are intentionally not stored in the current schema and are handled via safety guardrails.
- **Context Window**: SLM conversational history is kept concise to maintain the embedded sub-600 MB RAM budget.

### Future Work
- **Hardware Bus Binding**: Direct SocketCAN (`can0`) and Android Automotive AIDL VHAL integration on physical embedded test benches.
- **Domain Fine-Tuning**: Fine-tuning SLM weights on standardized SAE OBD-II and ISO 14229 UDS diagnostic codebooks.
- **Sensor Extension**: Expanding schema to support multi-zone TPMS and individual cell-level battery voltage telemetry.

---

## 📁 Project Directory Structure

```
vehicle_project/
├── analytics/         # Deterministic SQL calculation engine (comparisons, averages, ramps)
├── api/               # /api/chat query router and safety guardrails
├── data/              # Sample simulated and recorded vehicle trip datasets
├── database/          # SQLite schema, connection manager, and test scripts
├── docs/              # Comprehensive case study and edge performance reports
├── ingestion/         # Normalized schema, CSV loader, scenario simulator & bus adapters
├── llm/               # llama-cpp-python wrapper and factual prompting templates
├── models/            # Offline GGUF model storage (README with setup guide)
├── static/            # Dashboard styles, animations, and Chart.js assets
├── templates/         # Cockpit dashboard HTML template
├── tests/             # Automated test suite (62 test cases)
├── app.py             # Main Flask server entrypoint
├── requirements.txt   # Core Python dependencies
└── README.md          # Project landing documentation
```

*For complete implementation details, see [docs/PROJECT_COMPLETION_REPORT.md](docs/PROJECT_COMPLETION_REPORT.md) and [docs/EDGE_PERFORMANCE_REPORT.md](docs/EDGE_PERFORMANCE_REPORT.md).*
