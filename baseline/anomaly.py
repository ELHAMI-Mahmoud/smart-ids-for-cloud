"""Expérience Isolation Forest exclusivement synthétique, reproductible."""
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from smart_ids.pipeline import ROOT, detect

SEED = 42
BASE_FEATURES = ['flow_count', 'ports_out', 'destinations_out',
                 'max_ports_per_destination', 'bytes_out']


def generate_dataset(seed=SEED):
    """Chaque instance occupe une seule fenêtre ; aucune instance n'est recopiée."""
    rows = []
    for split_index, (split, day, count) in enumerate([
            ('train', '2026-01-01', 240), ('validation', '2026-01-03', 160),
            ('test', '2026-01-05', 160)]):
        rng = np.random.default_rng(seed + split_index)
        for i in range(count):
            suspicious = split != 'train' and i % 4 == 0
            kind = (['scan', 'fanout', 'exfiltration', 'subtle'][i // 4 % 4]
                    if suspicious else ['web', 'backup', 'interactive', 'download'][i % 4])
            # Variantes propres à chaque période, paramètres et tirages indépendants.
            variant = f'{split}:{kind}'
            window = pd.Timestamp(day, tz='UTC') + pd.Timedelta(minutes=5 * i)
            host = f'10.0.0.{10 + i % 5}'
            n = int(rng.integers(12, 35))
            if kind == 'scan':
                n = int(rng.integers(26 + split_index * 3, 65 + split_index * 4))
            elif kind == 'fanout':
                n = int(rng.integers(45 + split_index, 85 + split_index))
            elif kind == 'subtle':
                n = int(rng.integers(14, 22))
            total_out = int(rng.integers(100_000, 2_000_000))
            if kind == 'backup':
                total_out = int(rng.integers(60_000_000, 140_000_000))
            elif kind == 'exfiltration':
                total_out = int(rng.integers(160_000_000, 300_000_000))
            elif kind == 'subtle':
                total_out = int(rng.integers(10_000_000, 40_000_000))
            for j in range(n):
                direction = 'inbound' if j % 5 == 0 else 'outbound'
                peer = f'203.0.113.{1 + (j if kind == "fanout" else j % 3)}'
                port = (1000 + j + split_index * 100 if kind in ['scan', 'subtle']
                        else int(rng.choice([80, 443, 53])))
                size = total_out // (n - (n + 4) // 5)
                if direction == 'inbound':
                    size = int(rng.integers(1000, 100_000))
                    if kind == 'download':
                        size = int(rng.integers(2_000_000, 10_000_000))
                rows.append(dict(timestamp=window + pd.Timedelta(seconds=j),
                                 src_ip=host if direction == 'outbound' else peer,
                                 dst_ip=peer if direction == 'outbound' else host,
                                 dst_port=port, bytes=size, direction=direction,
                                 protocol='TCP', synthetic=True, split=split,
                                 scenario=variant, instance_id=f'{split}:{i}',
                                 label=int(suspicious)))
    return pd.DataFrame(rows)


def aggregate(flows):
    """Variables sans métadonnées : aucun label, scénario, split ou IP au modèle.

    direction est relative au périmètre interne. Absence de lignes entrantes ne
    prouve pas un volume entrant nul : bytes_in est alors omis du schéma.
    """
    df = flows.copy()
    if not df.direction.isin(['inbound', 'outbound']).all():
        raise ValueError('Direction inconnue : inbound/outbound requis.')
    if df['bytes'].isna().any() or (df['bytes'] < 0).any():
        raise ValueError('Volume manquant ou négatif.')
    df['window'] = pd.to_datetime(df.timestamp, utc=True).dt.floor('5min')
    df['host'] = np.where(df.direction.eq('outbound'), df.src_ip, df.dst_ip)
    inbound_available = df.direction.eq('inbound').any()
    rows = []
    for (window, host), g in df.groupby(['window', 'host'], sort=True):
        out = g[g.direction.eq('outbound')]
        ports = out.groupby('dst_ip').dst_port.nunique()
        row = dict(window=window, host=host, flow_count=len(g),
                   ports_out=out.dst_port.nunique(), destinations_out=out.dst_ip.nunique(),
                   max_ports_per_destination=int(ports.max()) if len(ports) else 0,
                   bytes_out=int(out['bytes'].sum()))
        if inbound_available:
            row['bytes_in'] = int(g.loc[g.direction.eq('inbound'), 'bytes'].sum())
        rows.append(row)
    return pd.DataFrame(rows)


def evaluation_windows(flows):
    features = aggregate(flows)
    df = flows.assign(window=pd.to_datetime(flows.timestamp, utc=True).dt.floor('5min'))
    df['host'] = np.where(df.direction.eq('outbound'), df.src_ip, df.dst_ip)
    for _, group in df.groupby(['window', 'host']):
        if any(group[c].nunique() != 1 for c in ['split', 'scenario', 'instance_id', 'label']):
            raise ValueError('Métadonnées incohérentes dans une fenêtre.')
    meta = df.groupby(['window', 'host'])[['split', 'scenario', 'instance_id', 'label']].first().reset_index()
    return features.merge(meta, on=['window', 'host'], validate='one_to_one')


def split_windows(windows):
    parts = {name: windows[windows.split.eq(name)].copy()
             for name in ['train', 'validation', 'test']}
    for name, part in parts.items():
        if part.empty:
            raise ValueError(f'Ensemble vide : {name}')
    if parts['train'].label.any():
        raise ValueError('Entraînement réservé au trafic normal.')
    for a, b in [('train', 'validation'), ('validation', 'test'), ('train', 'test')]:
        if parts[a].window.max() + pd.Timedelta(minutes=5) > parts[b].window.min():
            raise ValueError('Périodes chevauchantes ou ordre chronologique incorrect.')
        for col in ['instance_id', 'scenario']:
            if set(parts[a][col]) & set(parts[b][col]):
                raise ValueError(f'Fuite entre ensembles : {col}')
    return parts


def select_threshold(scores, labels):
    """F1 validation maximal ; égalité départagée par FPR minimal puis seuil haut."""
    if set(np.unique(labels)) != {0, 1}:
        raise ValueError('Validation : exemples normaux et suspects requis.')
    candidates = np.append(np.unique(scores), np.nextafter(max(scores), np.inf))
    ranked = []
    for threshold in candidates:
        report = metrics(labels, scores >= threshold)
        ranked.append((report['f1'], -report['false_positive_rate'], float(threshold)))
    return max(ranked)[2]


def metrics(labels, predictions):
    tn, fp, fn, tp = confusion_matrix(labels, predictions, labels=[0, 1]).ravel()
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, predictions, average='binary', zero_division=0)
    return dict(windows=len(labels), normal=int(tn + fp), suspicious=int(tp + fn),
                precision=float(precision), recall=float(recall), f1=float(f1),
                false_positive_rate=float(fp / (tn + fp)) if tn + fp else None,
                tn=int(tn), fp=int(fp), fn=int(fn), tp=int(tp))


def fit_detector(train, validation, features):
    if train.label.any():
        raise ValueError('Entraînement réservé au trafic normal.')
    model = IsolationForest(n_estimators=200, max_samples='auto',
                            contamination='auto', random_state=SEED, n_jobs=1)
    model.fit(train[features])
    threshold = select_threshold(-model.score_samples(validation[features]), validation.label)
    return model, threshold


def run_experiment(flows=None):
    flows = generate_dataset() if flows is None else flows
    windows = evaluation_windows(flows)
    parts = split_windows(windows)
    features = BASE_FEATURES + (['bytes_in'] if 'bytes_in' in windows else [])
    # Le test n'est transmis ni à fit_detector ni à select_threshold.
    model, threshold = fit_detector(parts['train'], parts['validation'], features)
    windows['anomaly_score'] = -model.score_samples(windows[features])
    windows['model_alert'] = windows.anomaly_score >= threshold
    rule_events = detect(flows)
    rule_keys = set(zip(rule_events.window, rule_events.src_ip))
    windows['rule_alert'] = [(w, h) in rule_keys for w, h in zip(windows.window, windows.host)]
    windows['combined_alert'] = windows.rule_alert | windows.model_alert
    reports = []
    for split in ['validation', 'test']:
        subset = windows[windows.split.eq(split)]
        for name in ['rule', 'model', 'combined']:
            reports.append(dict(split=split, detector=name,
                                **metrics(subset.label, subset[f'{name}_alert'])))
    return dict(windows=windows, metrics=pd.DataFrame(reports), threshold=threshold,
                features=features, model=model, rule_events=rule_events)


def main():
    flows = generate_dataset()
    result = run_experiment(flows)
    (ROOT / 'data').mkdir(exist_ok=True)
    (ROOT / 'reports').mkdir(exist_ok=True)
    flows.to_csv(ROOT / 'data/synthetic_ml_flows.csv', index=False)
    result['windows'].to_csv(ROOT / 'reports/synthetic_ml_windows.csv', index=False)
    result['metrics'].to_csv(ROOT / 'reports/synthetic_ml_metrics.csv', index=False)
    metadata = dict(seed=SEED, threshold=result['threshold'], features=result['features'],
                    model_parameters=result['model'].get_params(),
                    split_windows=result['windows'].groupby('split').size().to_dict(),
                    score='-IsolationForest.score_samples; non probabiliste',
                    threshold_selection='F1 validation, puis FPR minimal, puis seuil maximal',
                    combination='rule OR model', synthetic=True)
    (ROOT / 'reports/synthetic_ml_metadata.json').write_text(
        json.dumps(metadata, indent=2), encoding='utf-8')
    print('ÉVALUATION SUR DONNÉES SYNTHÉTIQUES UNIQUEMENT')
    print(f'Seuil validation : {result["threshold"]:.8f}')
    print(result['metrics'].to_string(index=False))


if __name__ == '__main__':
    main()
