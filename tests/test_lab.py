"""Vérification locale du protocole des données factices, pas de test cloud."""
import argparse
import threading
import unittest

from lab.send_test_traffic import private_target, transfer
from lab.tcp_sink import Server, Sink


class LabTests(unittest.TestCase):
    def test_sink_confirms_bytes_sent_by_observed_host(self):
        with Server(('127.0.0.1', 0), Sink) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                transfer('127.0.0.1', server.server_address[1], 1024)
            finally:
                server.shutdown()
                worker.join(timeout=5)

    def test_script_uses_private_lab_addresses(self):
        self.assertEqual(private_target('10.20.1.20'), '10.20.1.20')
        with self.assertRaises(argparse.ArgumentTypeError):
            private_target('8.8.8.8')
