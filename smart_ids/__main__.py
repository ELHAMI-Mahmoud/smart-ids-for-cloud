"""CLI du socle persistant : python -m smart_ids --help."""
import argparse
import json
import os
from pathlib import Path
import sqlite3

from smart_ids.config import AnalysisConfig
from smart_ids.exports import export_bundle
from smart_ids.pipeline import ROOT
from smart_ids.service import analyze_aws, analyze_synthetic
from smart_ids.storage import QUALIFICATIONS, STATUSES, Store


def main(argv=None):
    parser = argparse.ArgumentParser(description='Smart IDS local : import, historique et qualification. Aucun appel AWS.')
    parser.add_argument('--db', type=Path, default=Path(os.environ.get('SMART_IDS_DB', ROOT / 'var/smart_ids.sqlite3')))
    commands = parser.add_subparsers(dest='command', required=True)
    analyze = commands.add_parser('analyze', help='Importer des fichiers AWS dans l’historique')
    analyze.add_argument('files', nargs='+', type=Path)
    analyze.add_argument('--lab-cidr', action='append', required=True)
    analyze.add_argument('--interface-id', required=True)
    analyze.add_argument('--port-threshold', type=int, default=20)
    analyze.add_argument('--byte-threshold', type=int, default=50_000_000)
    analyze.add_argument('--window-policy', choices=['exclude', 'end'], default='exclude')
    analyze.add_argument('--output', type=Path)
    commands.add_parser('demo', help='Enregistrer la démonstration synthétique de référence')
    commands.add_parser('history', help='Lister les analyses enregistrées')
    export = commands.add_parser('export', help='Exporter une analyse complète')
    export.add_argument('analysis_id')
    export.add_argument('--output', type=Path, required=True)
    qualify = commands.add_parser('qualify', help='Qualifier une alerte sans changer sa décision')
    qualify.add_argument('alert_id')
    qualify.add_argument('--status', choices=STATUSES, required=True)
    qualify.add_argument('--qualification', choices=QUALIFICATIONS, required=True)
    qualify.add_argument('--comment', default='')
    args = parser.parse_args(argv)
    try:
        store = Store(args.db)
        if args.command == 'history':
            print(store.list_analyses().to_string(index=False))
            return
        if args.command == 'qualify':
            store.qualify(args.alert_id, args.status, args.qualification, args.comment)
            print('Qualification enregistrée.')
            return
        if args.command == 'analyze':
            config = AnalysisConfig(tuple(args.lab_cidr), args.interface_id, args.port_threshold,
                                    args.byte_threshold, args.window_policy)
            result, reused = analyze_aws([(p.name, p.read_bytes()) for p in args.files], config, store)
        elif args.command == 'demo':
            result, reused = analyze_synthetic(store)
        else:
            result, reused = store.load(args.analysis_id), True
        print(json.dumps(dict(id=result['id'], source=result['source'], reused=reused,
                              flows=len(result['flows']), alerts=len(result['alerts']),
                              config=result['config']), ensure_ascii=False, indent=2))
        if getattr(args, 'output', None):
            args.output.mkdir(parents=True, exist_ok=True)
            for name, payload in export_bundle(result).items():
                (args.output / name).write_bytes(payload)
    except (ValueError, LookupError, OSError, sqlite3.Error) as exc:
        parser.exit(2, f'Erreur : {exc}\n')


if __name__ == '__main__':
    main()
