import unittest

import pandas as pd

from smart_ids.pipeline import detect, generate_flows


class PipelineTests(unittest.TestCase):
    def test_reproducible_scenarios(self):
        flows = generate_flows()
        self.assertTrue(flows.equals(generate_flows()))
        self.assertEqual(len(flows), 945)
        alerts = detect(flows)
        self.assertEqual(set(alerts.src_ip), {'10.0.0.20', '10.0.0.30'})
        self.assertEqual(set(alerts.value), {40, 75_000_000})
        self.assertEqual(len(alerts), 2)

    def test_normal_and_empty(self):
        flows = generate_flows()
        self.assertTrue(detect(flows[flows.scenario.eq('normal')]).empty)
        self.assertTrue(detect(flows.iloc[:0]).empty)

    def test_boundaries_and_direction(self):
        flows = generate_flows()
        self.assertEqual(len(detect(flows, 40, 75_000_000)), 2)
        self.assertTrue(detect(flows, 41, 75_000_001).empty)
        flows['direction'] = 'inbound'
        self.assertTrue(detect(flows).empty)

    def test_labels_not_used(self):
        self.assertEqual(len(detect(generate_flows().drop(columns=['scenario', 'synthetic']))), 2)

    def test_scan_groups_destinations_and_windows(self):
        scan = generate_flows().query("scenario == 'port_scan'").copy()
        scan.loc[scan.index[20:], 'dst_ip'] = '198.51.100.6'
        self.assertTrue(detect(scan, 21).empty)
        scan['dst_ip'] = '198.51.100.5'
        scan.loc[scan.index[20:], 'timestamp'] += pd.Timedelta(minutes=5)
        self.assertTrue(detect(scan, 21).empty)


if __name__ == '__main__':
    unittest.main()
