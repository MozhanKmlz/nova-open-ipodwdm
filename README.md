# NOVA – Open IP-over-DWDM Orchestration Framework

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
[![GitHub release](https://img.shields.io/github/v/release/MozhanKmlz/nova-open-ipodwdm)](https://github.com/MozhanKmlz/nova-open-ipodwdm/releases)
![Cited By](https://img.shields.io/badge/Cited_by-0_papers-blue.svg)
![Last Commit](https://img.shields.io/github/last-commit/MozhanKmlz/nova-open-ipodwdm?color=blue)
![Stars](https://img.shields.io/github/stars/MozhanKmlz/nova-open-ipodwdm?style=social)

---

## Introduction

NOVA (Network Orchestration, Vigilance, and Automation) is an open-source orchestration framework that unifies OpenConfig and OpenROADM specifications to automate end-to-end Internet Protocol-over-Dense Wavelength Division Multiplexing (IPoDWDM) service creation, deletion, and telemetry collection across multi-vendor optical transport networks.

It has been validated in a multi-vendor testbed at The University of Texas at Dallas, enabling reproducible research in disaggregated optical networking.

### Key Features

- Unified orchestration across OpenROADM and OpenConfig
- Full automation for service creation and teardown
- Multi-vendor support
- OpenConfig lookup engine ensuring version-consistent payloads
- gNMI-based telemetry ingestion compatible with Prometheus and Grafana
- MongoDB-based persistence for payloads and device metadata
- Modular structure suitable for research, demos, and production-like environments

---

## Architecture

NOVA is composed of three main modules:

1. Hierarchical SDN Controller (H-SDNC)  
   Coordinates all service-related operations

2. End Terminal Controller (ETC) / IP Software Defined Networking Controller (IPSDNC)
   
   Manages routers, muxponders, and test equipment through OpenConfig

4. ROADM Network Controller (RNC)  
   Communicates with ROADMs via TransportPCE (TPCE)

All modules use model-driven APIs: RESTCONF, NETCONF, and gNMI. Kafka-based notifications provide asynchronous event updates.

---

## Installation

Clone the repository:
```bash
git clone https://github.com/MozhanKmlz/nova-open-ipodwdm.git
cd nova-open-ipodwdm
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Run the orchestrator:
```bash
python3.6 app.py
```
The orchestrator will be available at:
http://localhost:5000

## Usage
NOVA exposes two main orchestration endpoints:
```bash
POST /create-service
```
Executes the full workflow: performance info, temporary service creation, end terminal activation, service creation, and power setup.

```bash
POST /delete-service
```
Executes end terminal deactivation followed by service deletion.

### Create a Service
```bash
curl -X POST http://localhost:5000/create-service \
     -H "Content-Type: application/json" \
     -d '{
           "vendor": "#vendor",
           "component-name": "component-name",
           "frequency": 196081250000,
           "TxPower": 3
         }'
```

### Delete a Service
```bash
curl -X POST http://localhost:5000/delete-service \
     -H "Content-Type: application/json" \
     -d '{
           "vendor": "#vendor",
           "component-name": "OpticalChannel0/0/0/20",
           "frequency": 193100000000,
           "TxPower": -10
         }'
```
Note: Both endpoints require vendor, component-name, frequency, and TxPower because the activation and deactivation RPCs depend on them.

---

## Telemetry Pipeline
Supported telemetry mechanisms:
```bash
gNMI streaming using gNMIc

NETCONF exporters

Prometheus scraping

Grafana dashboards for visualization
```
--- 

## Project Structure
```
nova-open-ipodwdm/
│
├── orchestrator/ # NOVA top-level controller (H-SDNC)
├── controllers/ # Vendor ETC and RNC controller implementations
├── routes/ # HTTP API endpoints
├── utility/ # Helper functions and OpenConfig lookup engine
├── infra/ # MongoDB repository and storage logic
├── kafka_notif/ # Kafka consumer for TPCE events
└── app.py # Application entry point
```
---

## Citation

NOVA supports reproducible research in multi-vendor optical networking.  
Users of this framework are kindly asked to cite the following paper in any published work that builds upon this code:

**M. Kamalzadeh, A. G. Latha, T. Zhang, L. J. Horner, V. Gudepu, and A. Fumagalli,  
“Open Multi-Layer Orchestration Framework for Multi-Vendor IPoDWDM Transport Networks.”**

The complete citation record is provided in the `CITATION.cff` file.

This project is released under the MIT License. See the LICENSE file for more details.
