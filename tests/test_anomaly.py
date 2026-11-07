import unittest

import numpy as np
import pandas as pd

from smart_ids.anomaly import (BASE_FEATURES, aggregate, evaluation_windows,
                               generate_dataset, metrics,
                               run_experiment, split_windows)


class AnomalyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.flows = generate_dataset()
        cls.result = run_experiment(cls.flows)

    def test_reproducibility_and_splits(self):
        self.assertTrue(self.flows.equals(generate_dataset()))
        windows = self.result['windows']
        parts = split_windows(windows)
        self.assertEqual([len(parts[n]) for n in ['train', 'validation', 'test']], [240, 160, 160])
        self.assertFalse(parts['train'].label.any())
        self.assertEqual(parts['test'].label.sum(), 40)
        self.assertGreater(len(self.flows.query("split == 'train' and scenario == 'train:backup'")), 0)
        self.assertTrue((parts['train'].bytes_out >= 50_000_000).any())
        again = run_experiment(self.flows)
        np.testing.assert_array_equal(windows.anomaly_score, again['windows'].anomaly_score)
        self.assertEqual(self.result['threshold'], again['threshold'])

    def test_feature_allowlist_and_label_independence(self):
        bare = self.flows.drop(columns=['label', 'scenario', 'instance_id', 'split', 'synthetic'])
        pd.testing.assert_frame_equal(aggregate(bare), aggregate(self.flows))
        self.assertEqual(self.result['features'], BASE_FEATURES + ['bytes_in'])
        self.assertNotIn('host', self.result['features'])

    def test_test_labels_do_not_affect_fit_or_threshold(self):
        altered = self.flows.copy()
        altered.loc[altered.split.eq('test'), 'label'] = 1 - altered.loc[altered.split.eq('test'), 'label']
        altered.loc[altered.split.eq('test'), 'bytes'] *= 10
        changed = run_experiment(altered)
        self.assertEqual(changed['threshold'], self.result['threshold'])
        before_test = self.result['windows'].split.ne('test')
        np.testing.assert_array_equal(changed['windows'].loc[before_test, 'anomaly_score'],
                                      self.result['windows'].loc[before_test, 'anomaly_score'])

    def test_leakage_rejected(self):
        windows = evaluation_windows(self.flows)
        for col, value in [('window', windows.window.min()), ('instance_id', 'train:0'), ('scenario', 'train:web')]:
            bad = windows.copy()
            bad.loc[bad.split.eq('test'), col] = value
            with self.assertRaises(ValueError):
                split_windows(bad)
        bad = windows.copy()
        bad.loc[bad.split.eq('train'), 'label'] = 1
        with self.assertRaises(ValueError):
            split_windows(bad)

    def test_aggregation_direction_and_counts(self):
        sample = pd.DataFrame([
            dict(timestamp='2026-01-01T00:01Z', src_ip='10.0.0.1', dst_ip='203.0.113.1', direction='outbound', dst_port=443, bytes=100),
            dict(timestamp='2026-01-01T00:02Z', src_ip='203.0.113.1', dst_ip='10.0.0.1', direction='inbound', dst_port=1234, bytes=900),
        ])
        row = aggregate(sample).iloc[0]
        self.assertEqual((row.flow_count, row.ports_out, row.destinations_out, row.bytes_out, row.bytes_in), (2, 1, 1, 100, 900))
        self.assertNotIn('bytes_in', aggregate(sample.iloc[:1]).columns)

    def test_metrics_and_combination(self):
        m = metrics([0, 0, 1, 1], [0, 1, 0, 1])
        self.assertEqual((m['tn'], m['fp'], m['fn'], m['tp']), (1, 1, 1, 1))
        self.assertEqual(m['false_positive_rate'], .5)
        self.assertEqual(m['f1'], .5)
        w = self.result['windows']
        self.assertTrue((w.combined_alert == (w.rule_alert | w.model_alert)).all())
        self.assertTrue((self.result['metrics'].windows == 160).all())
