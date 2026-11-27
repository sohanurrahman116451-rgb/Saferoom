import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from server import Monitor, TCPServer, TCPHandler, UDPServer, UDPHandler, tcp_request

class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.monitor = Monitor(Path(self.temp.name)/'history.jsonl')
        self.tcp = TCPServer(('127.0.0.1', 0), TCPHandler)
        self.udp = UDPServer(('127.0.0.1', 0), UDPHandler)
        for server in (self.tcp, self.udp):
            server.monitor = self.monitor
            threading.Thread(target=server.serve_forever, daemon=True).start()
        self.port = self.tcp.server_address[1]

    def tearDown(self):
        for server in (self.tcp, self.udp):
            server.shutdown()
            server.server_close()
        self.temp.cleanup()

    def send(self, seq, temperature=23, smoke=2):
        packet=dict(room='Bedroom', sequence=seq, temperature=temperature, humidity=50, smoke=smoke)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            sender.sendto(json.dumps(packet).encode(), self.udp.server_address)
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            with self.monitor.lock:
                if self.monitor.rooms['Bedroom']['sequence']>=seq:
                    return
            time.sleep(.01)
        self.fail('UDP reading did not arrive')

    def test_udp_alert_tcp_ack_and_recovery(self):
        self.send(1, 44)
        state=tcp_request(self.port, {'action':'state'})
        self.assertEqual(state['rooms'][0]['status'], 'Critical')
        result=tcp_request(self.port, {'action':'ack','id':state['alerts'][0]['id']})
        self.assertTrue(result['alerts'][0]['acknowledged'])
        self.send(3)
        state=tcp_request(self.port, {'action':'state'})
        self.assertEqual(state['rooms'][0]['missing'],1)
        self.assertEqual(state['rooms'][0]['status'],'Normal')
        with self.monitor.lock:
            self.monitor.rooms['Bedroom']['last_seen']-=6
        self.assertEqual(tcp_request(self.port, {'action':'state'})['rooms'][0]['status'],'Offline')
        events=[json.loads(line) for line in self.monitor.history.read_text().splitlines()]
        self.assertTrue(any(e.get('event')=='acknowledgement' for e in events))

    def test_validation_and_split_tcp_frame(self):
        self.assertFalse(tcp_request(self.port, {'action':'scenario','room':'Bedroom','scenario':'invalid'})['ok'])
        with self.assertRaises(ValueError):
            self.monitor.receive(dict(room='Bedroom',sequence=1,temperature=float('nan'),humidity=50,smoke=0))
        with socket.create_connection(('127.0.0.1',self.port)) as connection:
            connection.sendall(b'{"action":')
            connection.sendall(b'"state"}\n')
            self.assertTrue(json.loads(connection.makefile('rb').readline())['ok'])

if __name__=='__main__':
    unittest.main()
