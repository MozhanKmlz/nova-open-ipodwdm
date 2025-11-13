# <img src="figures/Logo.png" align="right" height="80"/> NOVA – Open IP-over-DWDM Orchestration Framework

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.17546361.svg)](https://doi.org/10.5281/zenodo.17546361)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
[![GitHub release](https://img.shields.io/github/v/release/MozhanKmlz/nova-open-ipodwdm)](https://github.com/MozhanKmlz/nova-open-ipodwdm/releases)
![Cited By](https://img.shields.io/badge/Cited_by-0_papers-blue.svg)
![Last Commit](https://img.shields.io/github/last-commit/MozhanKmlz/nova-open-ipodwdm?color=blue)
![Stars](https://img.shields.io/github/stars/MozhanKmlz/nova-open-ipodwdm?style=social)

## Introduction

**NOVA** (*Network Orchestration, Vigilance, and Automation*) is an open-source orchestration framework that unifies **OpenConfig** and **OpenROADM** specifications to automate end-to-end IP-over-DWDM (IPoDWDM) service creation, deletion, and telemetry collection across **multi-vendor optical transport networks**.

This framework was developed at *The University of Texas at Dallas* and experimentally validated in a live multi-vendor testbed, demonstrating fully automated provisioning and telemetry between client devices and ROADMs. NOVA supports reproducible open research for disaggregated optical networks.

The system integrates open-source controllers, model-driven APIs, and real-time observability pipelines for deterministic, transparent, and vendor-agnostic orchestration.

**Main Features**

- Unified service automation across OpenROADM and OpenConfig devices  
- Multi-vendor support  
- OpenConfig lookup engine for version-consistent YANG payloads  
- gNMI-based telemetry streaming to Prometheus and Grafana  
- MongoDB persistence for payloads and configuration state  
- Extensible open-source architecture for reproducible research  

---

## Architecture

The NOVA framework follows a hierarchical architecture consisting of three controllers:

1. **Hierarchical SDN Controller (H-SDNC)** – top-level RESTCONF orchestrator coordinating all services  
2. **End Terminal Controller (ETC)** – manages routers, muxponders, and test sets using OpenConfig models  
3. **ROADM Network Controller (RNC)** – controls ROADMs and amplifiers through the open-source TransportPCE (TPCE)

All modules communicate through open APIs and event-driven Kafka notifications.  
Telemetry runs in parallel via containerized gNMIc collectors and Prometheus exporters.

---

## Installation

Clone the repository:

```bash
git clone https://github.com/MozhanKmlz/nova-open-ipodwdm.git
cd nova-open-ipodwdm
