"""Contrats, persistance, preuves et exports sur des journaux entièrement construits."""
import contextlib
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from smart_ids.__main__ import main
from smart_ids.config import AnalysisConfig
from smart_ids.exports import csv_bytes, export_bundle
from smart_ids.service import analyze_aws, analyze_synthetic, evidence
from smart_ids.storage import Store

ROOT = Path(__file__).resolve().parents[1]


def make_line(port=443, size=100, source='10.0.1.25', destination='203.0.113.7',
              action='ACCEPT', start=1767225610, end=1767225640):
    return f'2 111122223333 eni-lab1 {source} {destination} 41000 {port} 6 5 {size} {start} {end} {action} OK'


class ServiceTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'var').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'var')
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'history.sqlite3'
        self.store = Store(self.db)
        self.config = AnalysisConfig(('10.0.1.25/32',), 'eni-lab1')

    def analyze(self, lines, config=None, name='constructed.log'):
        return analyze_aws([(name, '\n'.join(lines).encode())], config or self.config, self.store)

    def test_config_contract_and_invalid_values(self):
        self.assertEqual(AnalysisConfig.from_dict(self.config.to_dict()), self.config)
        for values in [dict(port_threshold=0), dict(byte_threshold=True), dict(window_minutes=1),
                       dict(lab_cidrs=('0.0.0.0/0',)), dict(window_policy='guess'), dict(interface_id='bad'),
                       dict(schema_version=99)]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                AnalysisConfig.from_dict({**self.config.to_dict(), **values})

    def test_scan_boundaries_and_exact_evidence(self):
        first, _ = self.analyze([make_line(port=1000+i) for i in range(19)])
        self.assertTrue(first['alerts'].empty)
        result, _ = self.analyze([make_line(port=1000+i) for i in range(20)] + [
            make_line(source='203.0.113.7', destination='10.0.1.25', port=22)])
        alert = result['alerts'].iloc[0]
        self.assertEqual((alert.detector_id, alert.value, alert.threshold), ('R01', 20, 20))
        proof = evidence(result, alert.alert_id)
        self.assertEqual(len(proof), 20)
        self.assertTrue(proof.direction.eq('outbound').all())

    def test_volume_boundary_and_legitimate_qualification(self):
        quiet, _ = self.analyze([make_line(size=49_999_999)])
        self.assertTrue(quiet['alerts'].empty)
        result, _ = self.analyze([make_line(size=50_000_000)])
        alert = result['alerts'].iloc[0]
        before = evidence(result, alert.alert_id)
        self.store.qualify(alert.alert_id, 'Clôturé', 'Activité légitime', '=backup autorisé')
        reloaded = Store(self.db).load(result['id'])
        after = reloaded['alerts'].iloc[0]
        self.assertEqual(after.status, 'Clôturé')
        self.assertEqual(after.value, 50_000_000)
        pd.testing.assert_frame_equal(before, evidence(reloaded, alert.alert_id))
        self.assertEqual(len(self.store.followups(alert.alert_id)), 1)

    def test_identical_batch_reopens_after_restart_and_config_change_is_distinct(self):
        files = [('a.log', make_line().encode()), ('b.log.gz', gzip.compress(make_line(port=80).encode()))]
        first, reused = analyze_aws(files, self.config, self.store)
        self.assertFalse(reused)
        second, reused = analyze_aws(list(reversed(files)), self.config, Store(self.db))
        self.assertTrue(reused)
        self.assertEqual(first['id'], second['id'])
        changed = AnalysisConfig.from_dict({**self.config.to_dict(), 'port_threshold': 1})
        third, reused = analyze_aws(files, changed, self.store)
        self.assertFalse(reused)
        self.assertNotEqual(third['id'], first['id'])
        self.assertEqual(len(self.store.list_analyses()), 2)

    def test_empty_invalid_reject_and_cross_window_results_are_preserved(self):
        for lines, expected in [([], set()), (['bad line'], {'invalid'}),
                                ([make_line(action='REJECT')], {'rejected_traffic'}),
                                ([make_line(start=1767225890, end=1767225900)], {'cross_window_excluded'})]:
            with self.subTest(lines=lines):
                result, _ = self.analyze(lines)
                self.assertTrue(result['flows'].empty)
                self.assertTrue(result['alerts'].empty)
                self.assertEqual(set(result['diagnostics'].status), expected)
        approximate = AnalysisConfig.from_dict({**self.config.to_dict(), 'window_policy': 'end'})
        result, _ = self.analyze([make_line(start=1767225890, end=1767225900)], approximate)
        self.assertEqual(len(result['flows']), 1)
        self.assertTrue(result['flows'].crosses_windows.iloc[0])

    def test_exports_include_provenance_and_prevent_formulas(self):
        result, _ = self.analyze([make_line(size=50_000_000)], name='=HYPERLINK("bad").log')
        alert = result['alerts'].iloc[0]
        self.store.qualify(alert.alert_id, 'En cours', 'Non déterminé', '\t=1+1')
        outputs = export_bundle(self.store.load(result['id']))
        metadata = json.loads(outputs['metadata.json'])
        self.assertEqual(metadata['config'], self.config.to_dict())
        self.assertFalse(metadata['labeled'])
        self.assertFalse(metadata['ml_applied'])
        self.assertIn("'\t=1+1", outputs['alerts.csv'].decode('utf-8-sig'))
        self.assertIn("'=HYPERLINK", outputs['flows.csv'].decode('utf-8-sig'))
        parsed = pd.read_csv(io.BytesIO(outputs['windows.csv']))
        self.assertEqual(parsed.bytes_out.iloc[0], 50_000_000)

    def test_qualifying_nonexistent_or_invalid_status_changes_nothing(self):
        with self.assertRaises(LookupError):
            self.store.qualify('missing', 'Nouveau', 'Non déterminé')
        with self.assertRaises(ValueError):
            self.store.qualify('missing', 'malicious', 'Non déterminé')
        self.assertTrue(self.store.list_analyses().empty)

    def test_synthetic_origin_is_separate(self):
        synthetic, _ = analyze_synthetic(self.store)
        self.assertEqual(len(synthetic['alerts']), 2)
        self.analyze([make_line()])
        self.assertEqual(len(self.store.list_analyses('synthetic')), 1)
        self.assertEqual(len(self.store.list_analyses('aws_manual_import')), 1)
        self.assertTrue(json.loads(export_bundle(synthetic)['metadata.json'])['synthetic'])

    def test_persistence_preserves_numeric_looking_account_identifier(self):
        record = make_line().replace('111122223333', '001122334455')
        result, _ = self.analyze([record])
        self.assertEqual(result['flows'].account_id.iloc[0], '001122334455')

    def test_cli_uses_shared_configuration_and_exports(self):
        log = Path(self.temp.name) / 'constructed.log'
        log.write_text(make_line(), encoding='utf-8')
        output = Path(self.temp.name) / 'exports'
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            main(['--db', str(self.db), 'analyze', str(log), '--lab-cidr', '10.0.1.25/32',
                  '--interface-id', 'eni-lab1', '--port-threshold', '1', '--output', str(output)])
        result = json.loads(buffer.getvalue())
        self.assertEqual(result['alerts'], 1)
        metadata = json.loads((output / 'metadata.json').read_bytes())
        self.assertEqual(metadata['config']['port_threshold'], 1)


if __name__ == '__main__':
    unittest.main()
