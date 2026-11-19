"""Mesure locale sur 10 000 lignes AWS entièrement construites, sans appel cloud."""
import json
import platform
import sys
import tempfile
import time

from smart_ids.config import AnalysisConfig
from smart_ids.pipeline import ROOT
from smart_ids.service import analyze_aws
from smart_ids.storage import Store


def main():
    count = 10_000
    payload = '\n'.join(f'2 111122223333 eni-bench 10.0.1.25 203.0.113.7 {20000+i} '
                        f'{1000+i%40} 6 10 10000 1767225610 1767225640 ACCEPT OK'
                        for i in range(count)).encode()
    directory = ROOT / 'var'
    directory.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=directory) as temporary:
        store = Store(f'{temporary}/benchmark.sqlite3')
        started = time.perf_counter()
        result, _ = analyze_aws([('CONSTRUCTED-benchmark.log', payload)],
                               AnalysisConfig(('10.0.1.25/32',), 'eni-bench'), store)
        elapsed = time.perf_counter()-started
    print(json.dumps(dict(synthetic=True, actual_aws_capture=False, input_lines=count,
                          retained_records=len(result['flows']), alerts=len(result['alerts']),
                          elapsed_seconds=elapsed, target_seconds=30, target_met=elapsed < 30,
                          measurement='import, indicateurs, règles, stockage et relecture SQLite ; hors interface et ML',
                          python=sys.version.split()[0], platform=platform.platform(),
                          processor=platform.processor()), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
