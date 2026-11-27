# Development and learning record

## AI contribution

The student selected SafeRoom after discussing assignment ideas with Codex. Codex prepared the initial Python/socket implementation, dashboard, documentation and integration tests. Agentic AI was used for planning, file creation and automated verification. The student should record their own changes and explain the implementation honestly; do not describe AI-generated code as entirely hand-written.

## Learn in this order

1. Run the system and trigger each scenario.
2. Read `simulate` and identify the UDP socket and `sendto`.
3. Read `UDPHandler` and `Monitor.receive`: explain sequence numbers and validation.
4. Read `tcp_request` and `TCPHandler`: explain connection setup and newline framing.
5. Read `Monitor.evaluate`: explain thresholds and stale readings.
6. Trace one acknowledgement from `static/app.js` through HTTP and TCP to the event log.
7. Run the tests and record the actual results below.

## Student work log

| Date | What I changed/tested | Result / what I learned |
|---|---|---|
| | | |

## Submission checklist

- [ ] Add your name, student ID and course details.
- [ ] Run and understand every demo scenario.
- [ ] Run tests and record actual results.
- [ ] Capture a screenshot of your own dashboard.
- [ ] Upload source, static assets, README, tests and development log to GitHub.
- [ ] Download a clean ZIP and follow the README to verify reproducibility.
- [ ] Submit the repository URL and screenshot.

Suggested presentation: problem → three rooms → heat alert → TCP acknowledgement → normal recovery → UDP omissions → sensor offline → network architecture → AI contribution and limitations.
