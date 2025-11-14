# NOVA – Open IP-over-DWDM Orchestration Framework

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
[![GitHub release](https://img.shields.io/github/v/release/MozhanKmlz/nova-open-ipodwdm)](https://github.com/MozhanKmlz/nova-open-ipodwdm/releases)
![Cited By](https://img.shields.io/badge/Cited_by-0_papers-blue.svg)
![Last Commit](https://img.shields.io/github/last-commit/MozhanKmlz/nova-open-ipodwdm?color=blue)
![Stars](https://img.shields.io/github/stars/MozhanKmlz/nova-open-ipodwdm?style=social)

---

## Introduction

NOVA (Network Orchestration, Vigilance, and Automation) is an open-source orchestration framework that unifies OpenConfig and OpenROADM specifications to automate end-to-end IP-over-DWDM (IPoDWDM) service creation, deletion, and telemetry collection across multi-vendor optical transport networks.

It has been validated in a multi-vendor testbed at The University of Texas at Dallas, enabling reproducible research in disaggregated optical networking.

### Key Features

- Unified orchestration across OpenROADM and OpenConfig
- Full automation for service creation and teardown
- Multi-vendor support (Cisco, NEC, Anritsu, etc.)
- OpenConfig lookup engine ensuring version-consistent payloads
- gNMI-based telemetry ingestion compatible with Prometheus and Grafana
- MongoDB-based persistence for payloads and device metadata
- Modular structure suitable for research, demos, and production-like environments

---

## Architecture

NOVA is composed of three main modules:

1. Hierarchical SDN Controller (H-SDNC)  
   Coordinates all service-related operations

2. End Terminal Controller (ETC)  
   Manages routers, muxponders, and test equipment through OpenConfig

3. ROADM Network Controller (RNC)  
   Communicates with ROADMs via TransportPCE (TPCE)

All modules use model-driven APIs: RESTCONF, NETCONF, and gNMI. Kafka-based notifications provide asynchronous event updates.

---

## Installation

Clone the repository:

```bash
git clone https://github.com/MozhanKmlz/nova-open-ipodwdm.git
cd nova-open-ipodwdm


Install dependencies:

```bash
pip install -r requirements.txt


Run the orchestrator:

```bash
python app.py

The orchestrator will be available at:

http://localhost:5000


## USAGE
NOVA exposes two main orchestration endpoints:

POST /create-service
Executes the full workflow: performance info, temporary service creation, end terminal activation, service creation, and power setup.

POST /delete-service
Executes end terminal deactivation followed by service deletion.

Create a Service
bash
Copy code
curl -X POST http://localhost:5000/create-service \
     -H "Content-Type: application/json" \
     -d '{
           "vendor": "cisco",
           "component-name": "OpticalChannel0/0/0/20",
           "frequency": 193100000000,
           "TxPower": -3
         }'
Delete a Service
bash
Copy code
curl -X POST http://localhost:5000/delete-service \
     -H "Content-Type: application/json" \
     -d '{
           "vendor": "cisco",
           "component-name": "OpticalChannel0/0/0/20",
           "frequency": 193100000000,
           "TxPower": -30
         }'
Note: Both endpoints require vendor, component-name, frequency, and TxPower because the activation and deactivation RPCs depend on them.

Configuration
Configuration files are stored under:

arduino
Copy code
utility/config/
Included files:

ipsdnc.yaml
Vendor-specific OpenConfig controller settings

rnc.yaml
ROADM/TPCE controller configuration

kafka.yaml
Kafka consumer parameters

Payload files are retrieved from MongoDB using:

bash
Copy code
infra/persistence/repository.py
Telemetry Pipeline
Supported telemetry mechanisms:

gNMI streaming using gNMIc

NETCONF exporters

Prometheus scraping

Grafana dashboards for visualization

Available telemetry metrics:

Input and output optical power

OSNR

ESNR

Chromatic dispersion

Laser bias current

Polarization-dependent loss

Optical frequency and baud rate

Project Structure
graphql
Copy code
nova-open-ipodwdm/
│
├── orchestrator/        # NOVA top-level controller (H-SDNC)
├── controllers/         # Vendor ETC and RNC controller implementations
├── routes/              # HTTP API endpoints
├── utility/             # Helper functions and OpenConfig lookup engine
├── infra/               # MongoDB repository and storage logic
├── kafka_notif/         # Kafka consumer for TPCE events
└── app.py               # Application entry point
License
This project is released under the MIT License. See the LICENSE file for more details.
