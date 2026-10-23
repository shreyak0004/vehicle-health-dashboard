# VehicleGPT — Complete Project Implementation & Verification Report
**Tata Elxsi TELEPORT Season 4 — Case Study 5**  
**Local Project Directory:** `D:\My Projects\vehicle_project`  
**Date of Completion:** October 2026  
**Final Test Status:** **52 / 52 Passed (100%)**  

---

## 1. Project Purpose & Executive Overview

VehicleGPT is an offline, on-device natural-language vehicle health and diagnostics assistant designed for drivers and automotive service engineers. It bridges complex vehicle subsystems (CAN/CAN-FD, SOME/IP, Android Automotive VHAL, QNX syslog, ADAS, and UDS Diagnostics) with an offline Small Language Model (SLM), enabling ordinary language queries while enforcing strict factual integrity and read-only safety.

### Core Design Principle
> **The database and deterministic analytics establish the facts. The local language model explains those facts; it must never manufacture them.**

---

## 2. Implementation Status by Phase

| Phase | Description | Status | Verification & Evidence |
| :--- | :--- | :--- | :--- |
| **Phase 1** | Baseline Architecture & Flask API | **Complete** | SQLite storage, deterministic SQL calculations, routes intact. |
| **Phase 2** | Vehicle Scenario Simulation | **Complete** | Duplicate readings fixed (60 min = 60 readings). City trip persistence restored. Non-destructive `--reset` flag added. Overheating, low-battery, ADAS, cold weather verified. |
| **Phase 3** | Multi-Source Vehicle Ingestion | **Complete** | Common internal schema (`NormalizedTelemetry`, `NormalizedEvent`). Adapters for CAN/CAN-FD, SOME/IP, Android VHAL, QNX syslog, ADAS, Camera metadata, UDS Diagnostics. |
| **Phase 4** | Historical Retrieval & Safety Guardrails | **Complete** | Resolved tyre-pressure bug (unsupported signal handler). Added control command refusal (read-only safety perimeter). Added temporal root-cause disclaimer. |
| **Phase 5** | Offline Edge Deployment & Performance | **Complete** | Qwen2.5-0.5B-Q4_K_M running on 2 threads. RSS Memory: 561 MB (Budget: 2048 MB, 72.6% headroom). Instant SQL retrieval (< 3 ms). Automated benchmark script + report. |
| **Phase 6** | UI Refinement & End-to-End Demo | **Complete** | Floating round action button morphing to close icon. Smooth collapsible dashboard grid without gauge clipping. Collapse toggle for left sidebar. All 9 case-study queries verified end-to-end. |

---

## 3. Architecture & Data Flow

```
+--------------------------------------------------------------------------------------------------+
|                                    VEHICLE DATA SOURCES                                          |
|  [CAN / CAN-FD]   [SOME/IP]   [Android VHAL]   [QNX Syslog]   [ADAS Events]   [Camera Metadata]  |
+-----------------------------------+--------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------------------------------+
|                                  SOURCE-SPECIFIC ADAPTERS                                        |
|  ingestion/adapters/ (CAN, SOME/IP, VHAL, QNX, ADAS, Camera, Diagnostics)                       |
+-----------------------------------+--------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------------------------------+
|                          NORMALIZATION & VALIDATION ENGINE                                       |
|  - Ingestion Pipeline: Range bounds checking & unit normalization                                |
|  - Common Internal Schema: NormalizedTelemetry, NormalizedEvent                                  |
|  - Source provenance tracking (CAN, SOME/IP, VHAL, QNX, ADAS, CAMERA, DIAGNOSTICS)              |
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
|  1. Time Range Parsing: relative (yesterday, last 7 days) and absolute dates                     |
|  2. Safety Refusal Guard: blocks actuation/driving commands (ISO 26262 read-only)                |
|  3. Unsupported Signal Guard: rejects missing signals (e.g. tyre pressure) without hallucination |
|  4. Authoritative SQL Analytics: extremes, averages, trends, comparisons, anomalies, ramps       |
|  5. Event Investigation: retrieves preceding window with temporal disclaimer                     |
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
|  - Floating round FAB button with pulse ring and state morphing                                  |
|  - Collapsible dashboard layout contracting smoothly on chat open (Chart.resize())               |
|  - Real-time gauge metrics, 2D vehicle status, active telemetry graphs                           |
|  - Transparent source provenance & verified factual evidence tags                                |
+--------------------------------------------------------------------------------------------------+
```

---

## 4. Key Resolved Issues & Safety Safeguards

### 4.1 Simulator Duplicate Readings (Phase 2)
- **Problem:** `test_overheating_scenario.py` generated 120 readings for a 60-minute duration with each minute appearing twice.
- **Root Cause:** A duplicate iteration logic within the trip generator duplicated every minute's record.
- **Resolution:** Refactored `generate_trip` to calculate exact minute steps sequentially. 60 minutes now strictly yields 60 unique timestamped readings.

### 4.2 Lost Low-Battery Scenario & Safe Database Protection (Phase 2)
- **Problem:** In `generate_history()`, morning city trip records were overwritten by the subsequent highway trip assignment, causing planted low-battery events on `days_ago == 3` to be dropped. Furthermore, running `python -m ingestion.simulator` executed `init_db(reset=True)` destructively.
- **Resolution:** Fixed trip aggregation so morning city trips and evening highway trips are both appended to `all_readings` and `all_events`. Added safe `argparse` with `--reset` flag requirement to prevent accidental database wiping.

### 4.3 Unsupported Signal Bug: Tyre Pressure vs. Battery Temperature (Phase 4)
- **Problem:** When asked *"Are there any tyre pressure anomalies?"*, the system previously reported anomalies citing battery temperature readings (60.9 °C) because tyre pressure was absent from the schema and the engine defaulted to `battery_temp`.
- **Root Cause:** Intent detection identified `"anomaly"`, but column detection returned `None`. The anomaly handler defaulted to `column = "battery_temp"`.
- **Resolution:** Implemented `UNSUPPORTED_SIGNALS` detection ahead of anomaly routing. When an unsupported signal (tyre pressure, motor RPM, oil level, cabin climate, steering angle) is queried, the query engine immediately routes to `unsupported_signal`, bypasses LLM inference, and returns an explicit refusal listing all currently supported signals.

### 4.4 Vehicle Control Command Refusal (Phase 4)
- **Problem:** User could ask safety-critical action commands (e.g., *"Accelerate the vehicle to 100 km/h"*).
- **Resolution:** Added `CONTROL_COMMANDS` safety interceptor (`detect_control_command`). Rejects any driving, steering, braking, or actuation commands with an explicit read-only safety explanation conforming to automotive safety perimeters.

### 4.5 Causal Proof Disclaimer (Phase 4)
- **Problem:** When explaining warnings (e.g., *"Why did the vehicle record a battery overheating warning?"*), language models can confuse temporal correlation with mechanical causation.
- **Resolution:** Added explicit disclaimer to `handle_event_investigation`: *"The available data shows a temperature increase before the warning, but does not confirm a mechanical or electrical root cause."*

---

## 5. Offline Edge Benchmark & Target Hardware Analysis

Conducted via `python benchmark_edge_performance.py` pinned to `n_threads=2`:

| Metric | Target Specification | Measured Result | Status |
| :--- | :--- | :--- | :--- |
| **Max RAM Usage** | < 2048 MB (2.0 GB) | **561.2 MB Peak RSS** | **PASS (1486.8 MB Headroom)** |
| **Thread Pinning** | 2 ARM A5X-class cores | **2 threads pinned** (`n_threads=2`) | **PASS** |
| **SQL Retrieval Latency** | < 50 ms | **2.56 ms average** | **PASS (Instant)** |
| **Model Cold-Start Load** | < 5.0 s | **0.585 s** | **PASS** |
| **Warm SLM Inference Latency** | < 2.5 s (common queries) | **2.030 s average** | **PASS** |
| **Graceful Model Fallback** | Instant deterministic | **0.64 ms** | **PASS (Zero Downtime)** |
| **Offline Reliability** | 100% On-Device | **Zero network calls** | **PASS** |

---

## 6. End-to-End Test Suite Summary

Executed via `python -m pytest`:
```
============================= test session starts =============================
platform win32 -- Python 3.13.7, pytest-9.1.1, pluggy-1.7.0
rootdir: D:\My Projects\vehicle_project
collected 52 items

tests/test_analytics.py .............                                   [ 25%]
tests/test_end_to_end_demo.py ..........                                [ 44%]
tests/test_ingestion_adapters.py ........                               [ 59%]
tests/test_routing.py ..........                                         [ 78%]
tests/test_safety.py ......                                              [ 90%]
tests/test_scenarios.py .....                                            [100%]

============================= 52 passed in 20.86s =============================
```

---

## 7. Handover & Demonstration Commands

### 7.1 Running the Application
```powershell
cd "D:\My Projects\vehicle_project"
python app.py
```
Access the dashboard at `http://127.0.0.1:5000/`.

### 7.2 Running the Full Automated Test Suite
```powershell
python -m pytest -v
```

### 7.3 Running the Edge Performance Benchmark
```powershell
python benchmark_edge_performance.py
```

### 7.4 Safe Database Simulation / Re-seeding (Non-Destructive)
```powershell
# Safe check (refuses to overwrite existing database):
python -m ingestion.simulator

# Explicit re-seed (only when fresh 21-day dataset is desired):
python -m ingestion.simulator --reset --days 21
```

### 7.5 Tested Case-Study Questions for Demonstration
1. *"What was my average speed yesterday?"*  
   -> Returns deterministic average speed (~71.8 km/h) with AI explanation and evidence badge.
2. *"When was the battery temperature highest?"*  
   -> Returns highest temperature timestamp and value (2026-10-14 18:59:00, 60.9 °C).
3. *"Why did the vehicle record a battery overheating warning?"*  
   -> Displays temperature ramp from 37.3 °C to 55.1 °C with ambient/speed context and causation disclaimer.
4. *"How has energy efficiency changed over the last week?"*  
   -> Compares first-half and second-half consumption with cold-weather efficiency correlation.
5. *"Were there any ADAS disengagements yesterday?"*  
   -> Returns the 2 planted ADAS disengagements from yesterday with logged timestamps and reasons.
6. *"Are tyre-pressure readings available?"*  
   -> Returns explicit unsupported response; does **not** cite battery temperature.
7. *"Are there any tyre pressure anomalies?"*  
   -> Explains tyre pressure cannot be evaluated for anomalies because data is not in schema.
8. *"Accelerate the vehicle to 100 km/h"*  
   -> Safety refusal: Explains read-only diagnostics boundary and refuses control commands.
