# NOVA – Open IP-over-DWDM Orchestration Framework

![Logo](figures/nova_logo.png)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.17546361.svg)](https://doi.org/10.5281/zenodo.17546361)  
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)  
[![GitHub release](https://img.shields.io/github/v/release/MozhanKmlz/nova-open-ipodwdm)](https://github.com/MozhanKmlz/nova-open-ipodwdm/releases)  
![Last Commit](https://img.shields.io/github/last-commit/MozhanKmlz/nova-open-ipodwdm?color=blue)  
![Cited By](https://img.shields.io/badge/Cited_by-0_papers-blue.svg)  
![Stars](https://img.shields.io/github/stars/MozhanKmlz/nova-open-ipodwdm?style=social)

---

## Introduction

**NOVA** (*Network Orchestration, Vigilance, and Automation*) is an open-source orchestration framework that unifies **OpenConfig** and **OpenROADM** standards to automate end-to-end **IP-over-DWDM (IPoDWDM)** service creation, deletion, and telemetry collection across **multi-vendor optical transport networks**.

Developed at *The University of Texas at Dallas*, NOVA bridges IP and optical layers through open APIs, YANG models, and real-time telemetry, enabling reproducible and vendor-agnostic research.

### Key Features

- Automated IPoDWDM service provisioning and deletion  
- Multi-vendor support: Cisco, NEC, Ciena, Fujitsu, Anritsu  
- Hierarchical SDN Controller (H-SDNC) for cross-layer orchestration  
- OpenConfig Lookup Engine for YANG-model version consistency  
- MongoDB-based payload and state persistence  
- gNMI → Prometheus → Grafana telemetry pipeline  
- Extensible Python architecture for reproducible optical research  

---

## Architecture

![Architecture](figures/architecture.png)

**System Components:**

1. **Hierarchical SDN Controller (H-SDNC):** Orchestrates IP and optical domains.  
2. **IP-SDN Controller (IP-SDNC):** Manages routers, muxponders, and test sets using OpenConfig models.  
3. **ROADM Network Controller (RNC):** Controls ROADMs through the open-source TransportPCE (TPCE).  

Telemetry is continuously collected via gNMIc, exported to Prometheus, and visualized through Grafana dashboards.

---

## Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/MozhanKmlz/nova-open-ipodwdm.git
cd nova-open-ipodwdm
pip install -r requirements.txt
