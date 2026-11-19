"""Exports des résultats conservés, avec protection des champs CSV destinés à un tableur."""
import json

import pandas as pd


def csv_bytes(frame):
    def safe(value):
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False)
        if isinstance(value, str) and (value.startswith(('\t', '\r', '\n'))
                                       or value.lstrip().startswith(('=', '+', '-', '@'))):
            return "'"+value
        return value
    return frame.map(safe).to_csv(index=False).encode('utf-8-sig')


def export_bundle(analysis):
    metadata = {key: analysis[key] for key in ['id', 'source', 'created_at', 'engine_version',
                'config', 'files', 'elapsed_seconds']}
    metadata.update(timezone='UTC', labeled=False if analysis['source'] == 'aws_manual_import' else True,
                    synthetic=analysis['source'] == 'synthetic',
                    timestamp_policy='end; fenêtres fixes UTC de cinq minutes',
                    ml_applied=False)
    result = {f'{name}.csv': csv_bytes(analysis[name])
              for name in ['alerts', 'windows', 'diagnostics', 'flows']}
    result['metadata.json'] = json.dumps(metadata, ensure_ascii=False, indent=2).encode('utf-8')
    return result
