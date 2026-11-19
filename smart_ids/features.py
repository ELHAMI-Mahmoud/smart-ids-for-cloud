"""Indicateurs réseau partagés ; aucune dépendance à scikit-learn."""
import numpy as np
import pandas as pd

FEATURE_COLUMNS = ['flow_count', 'ports_out', 'destinations_out',
                   'max_ports_per_destination', 'bytes_out']


def aggregate(flows):
    """Une observation = un hôte interne dans une fenêtre fixe UTC de cinq minutes."""
    df = flows.copy()
    if df.empty:
        return pd.DataFrame(columns=['window', 'host', *FEATURE_COLUMNS])
    if not df.direction.isin(['inbound', 'outbound']).all():
        raise ValueError('Direction inconnue : inbound/outbound requis.')
    if df['bytes'].isna().any() or (df['bytes'] < 0).any():
        raise ValueError('Volume manquant ou négatif.')
    df['window'] = pd.to_datetime(df.timestamp, utc=True).dt.floor('5min')
    df['host'] = np.where(df.direction.eq('outbound'), df.src_ip, df.dst_ip)
    df['out_port'] = df.dst_port.where(df.direction.eq('outbound'))
    df['out_peer'] = df.dst_ip.where(df.direction.eq('outbound'))
    df['out_bytes'] = df['bytes'].where(df.direction.eq('outbound'), 0)
    df['in_bytes'] = df['bytes'].where(df.direction.eq('inbound'), 0)
    grouped = df.groupby(['window', 'host'], sort=True)
    result = grouped.agg(flow_count=('bytes', 'size'), ports_out=('out_port', 'nunique'),
                         destinations_out=('out_peer', 'nunique'), bytes_out=('out_bytes', 'sum'))
    per_peer = df.loc[df.direction.eq('outbound')].groupby(['window', 'host', 'dst_ip']).dst_port.nunique()
    maxima = per_peer.groupby(level=['window', 'host']).max()
    result['max_ports_per_destination'] = maxima.reindex(result.index, fill_value=0).astype('int64')
    if df.direction.eq('inbound').any():
        result['bytes_in'] = grouped.in_bytes.sum()
    columns = [*FEATURE_COLUMNS, *(['bytes_in'] if 'bytes_in' in result else [])]
    return result.reset_index()[['window', 'host', *columns]]
