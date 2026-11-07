import hashlib
import json
import unittest

import pandas as pd

from smart_ids.anomaly import aggregate
from smart_ids.audit import preserve_baseline
from smart_ids.pipeline import ROOT, detect


class AuditTests(unittest.TestCase):
    def test_snapshot_integrity(self):
        preserve_baseline()
        manifest = json.loads((ROOT / 'baseline/manifest.json').read_text())
        self.assertGreaterEqual(len(manifest), 6)
        for name, digest in manifest.items():
            self.assertEqual(hashlib.sha256((ROOT / 'baseline' / name).read_bytes()).hexdigest(), digest)

    def test_utc_boundary_host_and_bytes(self):
        # La seconde ligne est entrante pour le même hôte, pas pour son pair.
        rows = pd.DataFrame([
            dict(timestamp='2026-01-03T01:04:59+01:00', src_ip='10.0.0.1', dst_ip='203.0.113.1', direction='outbound', dst_port=443, bytes=50_000_000),
            dict(timestamp='2026-01-03T00:04:59Z', src_ip='203.0.113.1', dst_ip='10.0.0.1', direction='inbound', dst_port=1234, bytes=90_000_000),
            dict(timestamp='2026-01-03T00:05:00Z', src_ip='10.0.0.1', dst_ip='203.0.113.1', direction='outbound', dst_port=80, bytes=7),
            dict(timestamp='2026-01-03T00:04:59Z', src_ip='10.0.0.2', dst_ip='203.0.113.1', direction='outbound', dst_port=53, bytes=9),
        ])
        windows = aggregate(rows).set_index(['window', 'host'])
        first = windows.loc[(pd.Timestamp('2026-01-03T00:00Z'), '10.0.0.1')]
        second = windows.loc[(pd.Timestamp('2026-01-03T00:05Z'), '10.0.0.1')]
        self.assertEqual(len(windows), 3)
        self.assertEqual((first.flow_count, first.bytes_out, first.bytes_in, first.ports_out), (2, 50_000_000, 90_000_000, 1))
        self.assertEqual((second.bytes_out, second.bytes_in), (7, 0))
        alerts = detect(rows)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts.iloc[0].value, 50_000_000)
