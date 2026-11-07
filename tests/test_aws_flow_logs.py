import gzip
from pathlib import Path
import unittest

import pandas as pd

from smart_ids.anomaly import aggregate
from smart_ids.aws_flow_logs import DEFAULT_FIELDS, import_files

FIXTURE = Path(__file__).parent / 'fixtures/aws_v2_examples.log'


def line(**changes):
    record = dict(zip(DEFAULT_FIELDS, ('2 111122223333 eni-lab1 10.0.1.25 203.0.113.7 '
                                      '41000 443 6 5 7000 1767225610 1767225640 ACCEPT OK').split()))
    record.update(changes)
    return ' '.join(record[k] for k in DEFAULT_FIELDS)


def parse(text, **kwargs):
    return import_files([('example.log', text.encode())], ['10.0.1.25/32'], 'eni-lab1', **kwargs)


class AwsParserTests(unittest.TestCase):
    def test_official_default_example(self):
        # Premier exemple ACCEPT officiel AWS, sans constituer une capture réelle.
        result = import_files([('official-example.log', FIXTURE.read_bytes())],
                              ['172.31.16.21/32'], 'eni-1235b8ca123456789')
        self.assertEqual(len(result.flows), 1)
        row = result.flows.iloc[0]
        self.assertEqual((row.direction, row.bytes, row.packets, row.dst_port), ('inbound', 4249, 20, 22))
        self.assertEqual(row.timestamp, pd.Timestamp(1418530070, unit='s', tz='UTC'))
        self.assertNotIn('label', result.flows.columns)
        self.assertNotIn('scenario', result.flows.columns)

    def test_bidirectional_and_collection_status(self):
        result = import_files([('adapted-example.log', FIXTURE.read_bytes())], ['10.0.1.25/32'], 'eni-lab1')
        self.assertEqual(len(result.flows), 2)
        window = aggregate(result.flows).iloc[0]
        self.assertEqual((window.host, window.bytes_in, window.bytes_out), ('10.0.1.25', 12000, 7000))
        statuses = set(result.diagnostics.status)
        self.assertTrue({'nodata', 'skipdata', 'rejected_traffic', 'other_interface'}.issubset(statuses))

    def test_gzip_and_deduplication_across_files(self):
        payload = line().encode()
        result = import_files([('one.log', payload), ('two.log.gz', gzip.compress(payload))], ['10.0.1.25/32'], 'eni-lab1')
        self.assertEqual(len(result.flows), 1)
        self.assertEqual(result.diagnostics.status.tolist(), ['accepted', 'duplicate'])
        self.assertEqual(result.flows['bytes'].sum(), 7000)

    def test_unknown_and_invalid_fields_never_filled(self):
        for changes in [{'bytes': '-'}, {'bytes': '-1'}, {'packets': '0'}, {'dstport': '65536'},
                        {'srcaddr': '-'}, {'start': '1767225700'}, {'start': '1767225610000'},
                        {'bytes': str(2**63)}, {'protocol': '-'}, {'end': '9999999999999999999999'},
                        {'end': '4102444800'}, {'bytes': '1.5'}, {'action': 'UNKNOWN'}]:
            with self.subTest(changes=changes):
                result = parse(line(**changes))
                self.assertTrue(result.flows.empty)
                self.assertEqual(result.diagnostics.status.iloc[0], 'invalid')
        self.assertEqual(parse('bad line').diagnostics.status.iloc[0], 'invalid')

    def test_window_boundary_and_byte_conservation(self):
        text = line(start='1767225890', end='1767225900')
        self.assertTrue(parse(text).flows.empty)
        retained = parse(text, window_policy='end').flows.iloc[0]
        self.assertTrue(retained.crosses_windows)
        self.assertEqual(retained.timestamp, pd.Timestamp('2026-01-01T00:05:00Z'))
        self.assertEqual(retained.bytes, 7000)
        self.assertEqual(len(parse(line(start='1767225900', end='1767225900')).flows), 1)

    def test_scope_internal_external_ipv6_and_protocol(self):
        self.assertEqual(parse(line(dstaddr='10.0.1.25')).diagnostics.status.iloc[0], 'internal')
        self.assertEqual(parse(line(srcaddr='203.0.113.8')).diagnostics.status.iloc[0], 'outside')
        self.assertEqual(parse(line(protocol='1', srcport='0', dstport='0')).diagnostics.status.iloc[0], 'unsupported_protocol')
        v6 = line(srcaddr='2001:db8:1::25', dstaddr='2001:db8:2::7', protocol='17')
        result = import_files([('v6.log', v6.encode())], ['2001:db8:1::25/128'], 'eni-lab1')
        self.assertEqual(result.flows.direction.iloc[0], 'outbound')
        self.assertEqual(result.flows.protocol.iloc[0], 'UDP')
        for cidrs in [[], ['0.0.0.0/0'], ['10.0.1.25/24']]:
            with self.assertRaises(ValueError):
                import_files([], cidrs, 'eni-lab1')

    def test_custom_header_and_unsupported_formats(self):
        fields = list(reversed(DEFAULT_FIELDS)) + ['flow-direction']
        values = dict(zip(DEFAULT_FIELDS, line().split()))
        values.update({'version': '5', 'flow-direction': 'egress'})
        text = ' '.join(fields) + '\n' + ' '.join(values[k] for k in fields)
        self.assertEqual(len(parse(text).flows), 1)
        with self.assertRaises(ValueError):
            parse('version bytes start end\n2 10 20 30')
        result = import_files([('broken.gz', b'\x1f\x8bnotgzip'), ('bad.log', b'\xff')], ['10.0.1.25/32'], 'eni-lab1')
        self.assertTrue(result.flows.empty)
        self.assertTrue(result.diagnostics.status.eq('invalid_file').all())

    def test_no_silent_counter_overflow_or_empty_imputation(self):
        text = line(bytes=str(2**62)) + '\n' + line(bytes=str(2**62), dstport='80')
        with self.assertRaisesRegex(ValueError, 'int64'):
            parse(text)
        self.assertTrue(parse('').flows.empty)
        self.assertTrue(parse(line(bytes='0', packets='0')).flows['bytes'].eq(0).all())
