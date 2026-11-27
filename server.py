"""SafeRoom: real UDP telemetry and newline-framed TCP monitoring commands."""
import argparse
import json
import math
import random
import socket
import socketserver
import threading
import time
from collections import deque
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOMS = ['Bedroom', 'Kitchen', 'Server Room']


class Monitor:
    def __init__(self, history):
        self.lock = threading.RLock()
        self.history = Path(history)
        self.rooms = {name: dict(name=name, temperature=None, humidity=None, smoke=None,
                               last_seen=None, sequence=0, received=0, missing=0,
                               scenario='normal', drop=False, status='Waiting') for name in ROOMS}
        self.alerts = deque(maxlen=100)
        self.trace = deque(maxlen=20)
        self.counter = 0
        self.tcp_count = 0

    def log(self, protocol, message):
        self.trace.appendleft(dict(time=time.strftime('%H:%M:%S'), protocol=protocol, message=message))

    def alert(self, room, status, reason):
        self.counter += 1
        entry = dict(id=self.counter, time=time.strftime('%Y-%m-%d %H:%M:%S'), room=room,
                     status=status, reason=reason, acknowledged=False)
        # Persist before exposing the alert. Each line is independently readable JSON.
        with self.history.open('a') as output:
            output.write(json.dumps(entry) + '\n')
        self.alerts.appendleft(entry)
        self.log('ALERT', room + ': ' + reason)

    def evaluate(self, now):
        for room in self.rooms.values():
            if room['last_seen'] is None:
                continue
            if now - room['last_seen'] > 5:
                status, reason = 'Offline', 'No sensor readings for over 5 seconds'
            elif room['smoke'] >= 60 or room['temperature'] >= 40:
                status, reason = 'Critical', 'Smoke >= 60 demo units or temperature >= 40°C'
            elif room['temperature'] >= 30 or room['humidity'] >= 75:
                status, reason = 'Warning', 'Temperature >= 30°C or humidity >= 75%'
            else:
                status, reason = 'Normal', 'Readings returned to normal'
            if status != room['status']:
                previous = room['status']
                room['status'] = status
                if status != 'Normal' or previous not in ('Waiting', 'Normal'):
                    self.alert(room['name'], status, reason)

    def receive(self, packet):
        if not isinstance(packet, dict) or packet.get('room') not in self.rooms:
            raise ValueError('Unknown room')
        seq = packet.get('sequence')
        if type(seq) is not int or seq <= 0:
            raise ValueError('Invalid sequence')
        values = {}
        for key, low, high in [('temperature', -50, 150), ('humidity', 0, 100), ('smoke', 0, 100)]:
            value = packet.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError('Invalid ' + key)
            values[key] = value
        with self.lock:
            room = self.rooms[packet['room']]
            if seq <= room['sequence']:
                return  # Ignore duplicates and late datagrams.
            room['missing'] += max(0, seq - room['sequence'] - 1)
            room.update(values, sequence=seq, received=room['received'] + 1, last_seen=time.monotonic())
            self.log('UDP', '%s · reading #%d received' % (room['name'], seq))
            self.evaluate(time.monotonic())

    def command(self, request):
        if not isinstance(request, dict):
            raise ValueError('Expected JSON object')
        with self.lock:
            self.tcp_count += 1
            action = request.get('action', 'state')
            if action == 'scenario':
                room = self.rooms.get(request.get('room'))
                scenario = request.get('scenario')
                if room is None or scenario not in ('normal', 'heat', 'smoke', 'offline'):
                    raise ValueError('Invalid scenario')
                room['scenario'] = scenario
                self.log('TCP', room['name'] + ' · scenario: ' + scenario)
            elif action == 'drop':
                room = self.rooms.get(request.get('room'))
                if room is None or type(request.get('enabled')) is not bool:
                    raise ValueError('Invalid loss setting')
                room['drop'] = request['enabled']
                self.log('TCP', room['name'] + ' · simulated loss ' + str(room['drop']))
            elif action == 'ack':
                alert = next((a for a in self.alerts if a['id'] == request.get('id')), None)
                if alert is None:
                    raise ValueError('Alert not found')
                alert['acknowledged'] = True
                with self.history.open('a') as output:
                    output.write(json.dumps(dict(event='acknowledgement', id=alert['id'], time=time.time())) + '\n')
                self.log('TCP', 'Alert #%d acknowledged' % alert['id'])
            elif action != 'state':
                raise ValueError('Unknown action')
            now = time.monotonic()
            self.evaluate(now)
            rooms = [dict(r, age=None if r['last_seen'] is None else round(now-r['last_seen'], 1)) for r in self.rooms.values()]
            return dict(ok=True, rooms=rooms, alerts=list(self.alerts), trace=list(self.trace), tcp_count=self.tcp_count)


class UDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            self.server.monitor.receive(json.loads(self.request[0]))
        except (ValueError, TypeError, KeyError):
            pass


class TCPHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(3)
        try:
            frame = self.rfile.readline(8193)
            if len(frame) > 8192 or not frame.endswith(b'\n'):
                raise ValueError('Invalid newline-delimited frame')
            result = self.server.monitor.command(json.loads(frame))
        except (ValueError, TypeError, OSError) as error:
            result = dict(ok=False, error=str(error))
        self.wfile.write(json.dumps(result).encode() + b'\n')


class TCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class UDPServer(socketserver.UDPServer):
    allow_reuse_address = True


def tcp_request(port, request):
    with socket.create_connection(('127.0.0.1', port), timeout=4) as connection:
        connection.sendall(json.dumps(request).encode() + b'\n')
        with connection.makefile('rb') as stream:
            return json.loads(stream.readline(262144))


class WebHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent / 'static'), **kwargs)

    def do_POST(self):
        if self.path != '/api':
            self.send_error(404)
            return
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 8192:
                raise ValueError('Invalid request size')
            result = tcp_request(self.server.tcp_port, json.loads(self.rfile.read(size)))
            code = 200
        except (ValueError, TypeError, OSError) as error:
            result, code = dict(ok=False, error=str(error)), 400
        body = json.dumps(result).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def simulate(monitor, port, stop):
    sequences = dict.fromkeys(ROOMS, 0)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
        while not stop.is_set():
            for name in ROOMS:
                with monitor.lock:
                    scenario, drop = monitor.rooms[name]['scenario'], monitor.rooms[name]['drop']
                if scenario == 'offline':
                    continue
                sequences[name] += 1
                # Deterministic application-side omission, not an actual network fault.
                if drop and sequences[name] % 3 == 0:
                    continue
                packet = dict(room=name, sequence=sequences[name],
                              temperature=round((44 if scenario == 'heat' else 23) + random.uniform(-1, 1), 1),
                              humidity=round(random.uniform(43, 53), 1),
                              smoke=round(random.uniform(75, 90) if scenario == 'smoke' else random.uniform(0, 5), 1))
                sender.sendto(json.dumps(packet).encode(), ('127.0.0.1', port))
            stop.wait(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--tcp-port', type=int, default=9001)
    parser.add_argument('--udp-port', type=int, default=9002)
    args = parser.parse_args()
    stop = threading.Event()
    monitor = Monitor(Path(__file__).parent / 'alerts.jsonl')
    try:
        with TCPServer(('127.0.0.1', args.tcp_port), TCPHandler) as tcp, UDPServer(('127.0.0.1', args.udp_port), UDPHandler) as udp, ThreadingHTTPServer(('127.0.0.1', args.port), WebHandler) as web:
            tcp.monitor = udp.monitor = monitor
            web.tcp_port = tcp.server_address[1]
            for backend in (tcp, udp):
                threading.Thread(target=backend.serve_forever, daemon=True).start()
            worker = threading.Thread(target=simulate, args=(monitor, udp.server_address[1], stop), daemon=True)
            worker.start()
            print('SafeRoom: http://localhost:%d' % web.server_address[1], flush=True)
            print('TCP commands :%d | UDP telemetry :%d | Ctrl+C to stop' % (args.tcp_port, args.udp_port), flush=True)
            try:
                web.serve_forever()
            finally:
                stop.set()
                worker.join(2)
                tcp.shutdown()
                udp.shutdown()
    except KeyboardInterrupt:
        print('\nSafeRoom stopped.')
    except OSError as error:
        parser.exit(1, 'Cannot start SafeRoom: %s\nTry a different --port, --tcp-port or --udp-port.\n' % error)


if __name__ == '__main__':
    main()
