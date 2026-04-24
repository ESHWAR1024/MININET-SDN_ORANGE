ALL THE SCREENSHOTS ARE :- PORT_STATUS , TOPOLOGY AND THE CONTOLLER STATUS DISPLAY

1)
<img width="1171" height="634" alt="image" src="https://github.com/user-attachments/assets/35571715-4781-42e5-93e0-e8136bdc602e" />
<img width="1171" height="601" alt="image" src="https://github.com/user-attachments/assets/f7c7a71e-9402-481b-a481-935183ae505d" />


2)
<img width="1171" height="634" alt="image" src="https://github.com/user-attachments/assets/1d991c2f-29fe-4075-bc33-b8d71d835003" />


3)
<img width="1171" height="634" alt="image" src="https://github.com/user-attachments/assets/2041097b-90df-4fb6-bc8a-9e8425f44656" />


# Port Status Monitoring Tool — SDN Mininet Project

![SDN](https://img.shields.io/badge/SDN-OpenFlow%201.3-blue)
![Controller](https://img.shields.io/badge/Controller-Ryu-orange)
![Emulator](https://img.shields.io/badge/Emulator-Mininet-green)
![Python](https://img.shields.io/badge/Python-3.11-yellow)

## Problem Statement

In traditional networks, administrators have no centralized visibility into switch port states. A link failure can go undetected until end users report connectivity issues — by which time it's too late.

This project implements an **SDN-based Port Status Monitoring Tool** using Mininet and a Ryu OpenFlow 1.3 controller. The controller monitors every switch port in real time, detects link up/down events the moment they happen, logs all changes with timestamps, generates alerts, and exposes a live REST API for status display.

---

## Topology

```
  h1 (10.0.0.1) ──┐
                   s1 ───[monitored link]─── s2
  h2 (10.0.0.2) ──┘                          ├── h3 (10.0.0.3)
                                              └── h4 (10.0.0.4)

  Controller (Ryu) ── OpenFlow 1.3 ──► s1, s2
  REST API: http://127.0.0.1:8080/status
```

| Component | Role |
|-----------|------|
| Ryu Controller | Handles OpenFlow events, installs flow rules, monitors ports |
| s1, s2 | OVS software switches running OpenFlow 1.3 |
| h1–h4 | Hosts used for ping and iperf testing |
| Inter-switch link | The primary monitored link — toggled for failure simulation |

---

## Features

- Real-time **port up/down detection** via `EventOFPPortStatus`
- **Timestamped logging** of every port change to `port_status.log`
- **Alert generation** for LINK_DOWN (WARNING) and LINK_UP (INFO) events
- **MAC learning switch** with automatic flow rule installation
- **REST API** with three endpoints for live status, alerts, and change log
- **Live CLI display** showing all port states and recent alerts with color coding

---

## Project Structure

```
port-status-monitor/
├── port_monitor.py       # Ryu controller — core SDN logic
├── topology.py           # Mininet custom topology (2 switches, 4 hosts)
├── display_status.py     # Live CLI status viewer
├── port_status.log       # Auto-generated log file (created at runtime)
├── README.md
└── screenshots/
    ├── 01_controller_start.png
    ├── 02_topology_start.png
    ├── 03_pingall.png
    ├── 04_flow_tables.png
    ├── 05_iperf_result.png
    ├── 06_rest_api_status.png
    ├── 07_link_down_alert.png
    ├── 08_status_display_down.png
    ├── 09_link_up_restored.png
    ├── 10_ping_recovery.png
    ├── 11_alerts_json.png
    └── 12_port_stats.png
```

---

## Setup & Installation

### Prerequisites

```bash
sudo apt-get update
sudo apt-get install -y mininet wireshark tshark iperf3 curl
sudo service openvswitch-switch start
```

### Python environment (Python 3.11 required — Ryu is incompatible with 3.12+)

```bash
python3.11 -m venv ~/sdn-env
source ~/sdn-env/bin/activate
pip install --upgrade pip
pip install eventlet==0.30.2 ryu requests
```

---

## Running the Project

Follow this exact order every time.

### Step 1 — Clean up any previous Mininet state

```bash
sudo mn -c
```

### Step 2 — Start the Ryu controller (Terminal 1)

```bash
source ~/sdn-env/bin/activate
cd ~/port-status-monitor
ryu-manager port_monitor.py --observe-links --wsapi-port 8080
```

Wait until you see:
```
Port Status Monitoring Tool — Controller Started
REST API: http://127.0.0.1:8080/status
```

### Step 3 — Start Mininet topology (Terminal 2)

```bash
cd ~/port-status-monitor
sudo python3 topology.py
```

### Step 4 — Start the live display (Terminal 3)

```bash
source ~/sdn-env/bin/activate
cd ~/port-status-monitor
python3 display_status.py
```

---

## Test Scenarios

### Scenario 1 — Normal forwarding and flow rule installation

Run in the Mininet CLI (`mininet>` prompt):

```bash
mininet> pingall
mininet> h1 ping -c 5 h3
mininet> iperf h1 h3
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s1
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s2
```

Expected results:
- `pingall` shows 0% dropped — all 4 hosts reach each other
- Flow rules are installed on both switches after first ping
- iperf shows throughput between h1 and h3

### Scenario 2 — Link failure detection and recovery

```bash
# Bring down the inter-switch link
mininet> link s1 s2 down
```

Expected: Controller immediately logs a WARNING alert for LINK_DOWN on the inter-switch port. Display shows port in RED.

```bash
# Restore the link
mininet> link s1 s2 up
```

Expected: Controller logs INFO alert for LINK_UP. Display shows port GREEN again.

```bash
# Verify traffic recovers
mininet> h1 ping -c 3 h3
```

---

## REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Live port states for all switches + recent alerts |
| `/alerts` | GET | All generated alerts with timestamps |
| `/log` | GET | Complete port change history |

```bash
curl http://127.0.0.1:8080/status  | python3 -m json.tool
curl http://127.0.0.1:8080/alerts  | python3 -m json.tool
curl http://127.0.0.1:8080/log     | python3 -m json.tool
```

---

## Expected Output

### pingall
```
*** Ping: testing ping reachability
h1 -> h2 h3 h4
h2 -> h1 h3 h4
h3 -> h1 h2 h4
h4 -> h1 h2 h3
*** Results: 0% dropped (12/12 received)
```

### Controller alert on link down
```
=======================================================
  !! ALERT [WARNING] LINK_DOWN | Switch 1 | Port 3 (s1-eth3) | 2026-04-24 11:30:00
=======================================================
```

### REST API /status
```json
{
  "port_status": {
    "1": {
      "1": { "name": "s1-eth1", "state": "UP", "up_events": 1, "down_events": 0 },
      "2": { "name": "s1-eth2", "state": "UP", "up_events": 1, "down_events": 0 },
      "3": { "name": "s1-eth3", "state": "UP", "up_events": 1, "down_events": 0 }
    }
  },
  "alert_count": 2,
  "recent_alerts": [...]
}
```

---

## References

- Ryu SDN Framework Documentation — https://ryu.readthedocs.io
- OpenFlow 1.3 Specification — https://opennetworking.org/wp-content/uploads/2014/10/openflow-spec-v1.3.0.pdf
- Mininet Walkthrough — http://mininet.org/walkthrough
- Open vSwitch Documentation — https://docs.openvswitch.org


