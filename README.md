# SafeRoom — Environment Alert Dashboard

Assignment 4: simulated room monitoring using real UDP telemetry and TCP commands/alert retrieval. Built with agentic AI assistance (Codex), Python's standard library, HTML, CSS and JavaScript. No hardware, packages, database or API keys required. Python 3.9+.

## 1. Run on macOS

Open Terminal, change into this project folder and run:

```sh
cd /Users/sohanurrahman/Documents/ChatGPT/cn/saferoom
python3 server.py
```

Open **http://localhost:8000** in Safari or Chrome. Keep Terminal running. Stop with **Control+C**.

For evaluators: download and extract the repository ZIP, open Terminal in the extracted folder (the one containing server.py), and run `python3 server.py`. On Windows, `python server.py` may be used. No installation step beyond Python is required.

If ports are in use:

```sh
python3 server.py --port 8080 --tcp-port 9101 --udp-port 9102
```

Open http://localhost:8080. The footer shows default port labels; startup output is authoritative for custom ports.

## 2. Demonstrate

1. Observe three rooms reporting about once per second.
2. Choose **Simulate overheating** for Bedroom. A critical alert appears on the next reading.
3. Acknowledge the alert. This travels through the TCP backend; acknowledgement means seen, not that conditions are safe.
4. Restore normal conditions. A recovery event appears.
5. Choose **Simulate smoke** for Kitchen. Smoke uses illustrative 0–100 demo units, not calibrated measurements.
6. Enable **Omit every third UDP reading**. Watch sequence gaps increase after the next received reading. This is deliberate application-side omission, not proof of network packet loss.
7. Choose **Disconnect sensor**. After over five seconds without readings, the room becomes Offline. Last values remain visible but are stale.
8. Capture the screen with Command+Shift+4 and save it as `docs/screenshot.png`.

## 3. Network implementation

```text
Sensor simulator -- JSON UDP datagrams :9002 --> UDP receiver --> room state
Browser -- HTTP over TCP :8000 --> web gateway
Web gateway -- newline-delimited JSON TCP :9001 --> monitoring backend
Monitoring backend -- JSON response, including alerts --> gateway --> browser
```

The simulator uses `socket(AF_INET, SOCK_DGRAM)` and `sendto`. UDP preserves datagram boundaries and has no delivery/order guarantee. Per-room sequence numbers detect gaps; late and duplicate readings are ignored. Gaps can also reflect reordering, so the counter is not a precise packet-loss measurement.

The gateway uses `socket.create_connection` and `sendall`. The TCP backend uses `ThreadingTCPServer`. TCP is an ordered byte stream; newline framing identifies a complete JSON request even when delivered in separate reads. Commands receive an application response. TCP transport reliability does not guarantee an application processed a command: clients still need to inspect responses.

The browser polls once per second. Alerts are retrieved in TCP responses, not pushed over a persistent alert connection. Scenario commands control the in-process simulator through shared state. All actual sensor measurements still travel over UDP. A lock protects concurrent state access.

Thresholds: Warning at temperature >=30°C or humidity >=75%; Critical at temperature >=40°C or smoke >=60 demo units; Offline after >5 seconds without readings. Thresholds are illustrative and shared across rooms.

## 4. Test

```sh
python3 -m unittest -v
```

Tests use real local TCP/UDP sockets and check critical alerts, TCP acknowledgement, recovery, sequence gaps, stale sensors, malformed readings and split TCP writes.

## 5. Files

- `server.py`: simulator, UDP receiver, TCP backend and HTTP gateway.
- `static/`: dashboard interface.
- `test_server.py`: integration tests.
- `DEVELOPMENT.md`: AI-use record and submission checklist.
- `alerts.jsonl`: generated event and acknowledgement log. Not included in source control.

## Limits

Educational prototype, not a fire alarm or certified safety system. Loopback-only, single-process classroom demo. No authentication or TLS; do not expose it publicly. Latest 100 alerts are held in memory. Events are appended to disk, but dashboard history, acknowledgement state, IDs and counters reset on restart; old log records are not reloaded. Logging errors need investigation (check Terminal and disk permissions). Random simulated data is not a real sensor feed.

## Publish and submit

Create a GitHub account and a new repository named `saferoom`. Through the GitHub website choose **Add file → Upload files** and upload the contents of this folder, preserving `static/`. Exclude `__pycache__/` and generated `alerts.jsonl`. Include a screenshot of your actual run, your name/course details and any required report. Download your own repository ZIP and verify the run instructions from a clean extraction before submitting its URL. GitHub Pages cannot execute this Python backend; the repository is for downloading and running locally.
