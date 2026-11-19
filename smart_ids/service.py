"""Chaîne commune import, détection, justification et persistance. Aucun appel cloud."""
import hashlib
import json
import time
import uuid

import pandas as pd

from smart_ids.aws_flow_logs import import_files
from smart_ids.config import AnalysisConfig, ENGINE_VERSION
from smart_ids.features import aggregate
from smart_ids.pipeline import detect, generate_flows
from smart_ids.storage import utc_now


def _decisions(flows, config, analysis_id):
    alerts = detect(flows, config.port_threshold, config.byte_threshold)
    if alerts.empty:
        return alerts
    windows = pd.to_datetime(flows.timestamp, utc=True).dt.floor('5min')
    for index, row in alerts.iterrows():
        detector = 'R01' if row.rule == 'Scan de ports' else 'R02'
        alerts.at[index, 'detector_id'] = detector
        alerts.at[index, 'alert_id'] = str(uuid.uuid5(uuid.UUID(analysis_id), f'{detector}:{row.window}:{row.src_ip}:{row.dst_ip}'))
    alerts['evidence_ids'] = [flows.loc[(windows.eq(row.window) & flows.src_ip.eq(row.src_ip)
        & flows.direction.eq('outbound') & (flows.dst_ip.eq(row.dst_ip) if row.detector_id == 'R01' else True)),
        'event_id'].tolist() for row in alerts.itertuples()]
    return alerts


def _save(store, source, config, files, identity, flows, diagnostics, started):
    flows = flows.reset_index(drop=True).copy()
    flows['event_id'] = range(len(flows))
    analysis_id = str(uuid.uuid4())
    alerts = _decisions(flows, config, analysis_id)
    analysis = dict(id=analysis_id, identity=identity, source=source, created_at=utc_now(),
                    engine_version=ENGINE_VERSION, config=config.to_dict(), files=files,
                    flows=flows, windows=aggregate(flows), diagnostics=diagnostics,
                    alerts=alerts, elapsed_seconds=time.perf_counter()-started)
    saved_id, reused = store.save(analysis)
    return store.load(saved_id), reused


def analyze_aws(files, config, store):
    if not isinstance(config, AnalysisConfig):
        raise ValueError('AnalysisConfig attendu.')
    started = time.perf_counter()
    if not files:
        raise ValueError('Choisir au moins un fichier de journaux.')
    files = list(files)
    if any(not isinstance(name, str) or not 1 <= len(name) <= 255 or not isinstance(payload, bytes)
           for name, payload in files):
        raise ValueError('Chaque fichier doit avoir un nom de 1 à 255 caractères et un contenu en octets.')
    # Même ordre de traitement quel que soit l'ordre de sélection dans l'interface.
    files.sort(key=lambda f: (f[0], hashlib.sha256(f[1]).hexdigest()))
    manifest = [dict(name=name, sha256=hashlib.sha256(payload).hexdigest(), size=len(payload))
                for name, payload in files]
    identity = hashlib.sha256(json.dumps(dict(source='aws_manual_import', version=ENGINE_VERSION,
        config=config.to_dict(), files=manifest), sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    existing = store.find_identity(identity)
    if existing:
        return store.load(existing), True
    result = import_files(files, config.lab_cidrs, config.interface_id, config.window_policy)
    return _save(store, 'aws_manual_import', config, manifest, identity, result.flows, result.diagnostics, started)


def analyze_synthetic(store, port_threshold=20, byte_threshold=50_000_000):
    started = time.perf_counter()
    config = AnalysisConfig(('10.0.0.0/24',), 'eni-synthetic', port_threshold, byte_threshold)
    identity = hashlib.sha256(('synthetic-demo-v1:'+ENGINE_VERSION+config.canonical_json()).encode()).hexdigest()
    existing = store.find_identity(identity)
    if existing:
        return store.load(existing), True
    return _save(store, 'synthetic', config, [], identity, generate_flows(),
                 pd.DataFrame(columns=['source_file', 'source_line', 'status', 'reason']), started)


def evidence(analysis, alert_id):
    alerts = analysis['alerts']
    chosen = alerts.loc[alerts.alert_id.eq(alert_id)] if not alerts.empty else alerts
    if chosen.empty:
        raise LookupError('Alerte introuvable dans cette analyse.')
    return analysis['flows'].loc[analysis['flows'].event_id.isin(chosen.iloc[0].evidence_ids)].copy()
