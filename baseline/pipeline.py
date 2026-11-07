"""Génération reproductible et règles locales, sans accès réseau."""
from pathlib import Path
import random

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def generate_flows(seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    start = pd.Timestamp('2026-01-01T10:00:00Z')
    rows = []

    def add(minute, src, dst, port, size, scenario):
        rows.append(dict(timestamp=start + pd.Timedelta(minutes=minute),
                         src_ip=src, dst_ip=dst, dst_port=port, bytes=size,
                         direction='outbound', protocol='TCP',
                         synthetic=True, scenario=scenario))

    for minute in range(60):
        for host in range(10, 15):
            for _ in range(3):
                add(minute, f'10.0.0.{host}', '203.0.113.10',
                    rng.choice([53, 80, 443]), rng.randint(1000, 50000), 'normal')
    for port in range(1, 41):
        add(12, '10.0.0.20', '198.51.100.5', port, 100, 'port_scan')
    for minute in range(30, 35):
        add(minute, '10.0.0.30', '203.0.113.20', 443, 15_000_000,
            'outbound_volume')
    return pd.DataFrame(rows)


def detect(flows: pd.DataFrame, port_threshold: int = 20,
           byte_threshold: int = 50_000_000) -> pd.DataFrame:
    """Fenêtres fixes UTC de 5 min ; seuils inclusifs, trafic sortant uniquement.

    Le scan mesure les ports distincts par source ET destination.
    Le volume est cumulé par source sur toutes les destinations.
    Les étiquettes de scénario ne sont jamais utilisées pour détecter.
    """
    if port_threshold < 1 or byte_threshold < 1:
        raise ValueError('Les seuils doivent être strictement positifs.')
    df = flows.loc[flows['direction'].eq('outbound')].copy()
    df['window'] = pd.to_datetime(df['timestamp'], utc=True).dt.floor('5min')
    alerts = []
    for (window, src, dst), group in df.groupby(['window', 'src_ip', 'dst_ip']):
        ports = group['dst_port'].nunique()
        if ports >= port_threshold:
            alerts.append(dict(window=window, src_ip=src, dst_ip=dst,
                               rule='Scan de ports', value=int(ports),
                               threshold=port_threshold, unit='ports distincts'))
    for (window, src), group in df.groupby(['window', 'src_ip']):
        volume = group['bytes'].sum()
        if volume >= byte_threshold:
            alerts.append(dict(window=window, src_ip=src, dst_ip='Toutes',
                               rule='Volume sortant', value=int(volume),
                               threshold=byte_threshold, unit='octets'))
    return pd.DataFrame(alerts, columns=['window', 'src_ip', 'dst_ip', 'rule',
                                       'value', 'threshold', 'unit'])


def main():
    flows = generate_flows()
    alerts = detect(flows)
    (ROOT / 'data').mkdir(exist_ok=True)
    (ROOT / 'reports').mkdir(exist_ok=True)
    flows.to_csv(ROOT / 'data/synthetic_flows.csv', index=False)
    alerts.to_csv(ROOT / 'reports/synthetic_alerts.csv', index=False)
    print(f'DONNÉES SYNTHÉTIQUES : {len(flows)} flux, {len(alerts)} alertes.')
    print(alerts.to_string(index=False))


if __name__ == '__main__':
    main()
