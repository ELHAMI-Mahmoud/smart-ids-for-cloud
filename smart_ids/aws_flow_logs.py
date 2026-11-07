"""Import manuel VPC Flow Logs texte/gzip. Aucun appel AWS, aucun entraînement."""
import argparse
from dataclasses import dataclass
import gzip
import io
import json
import ipaddress
from pathlib import Path
import re
import zlib

import pandas as pd

from smart_ids.pipeline import detect

DEFAULT_FIELDS = ('version account-id interface-id srcaddr dstaddr srcport dstport '
                  'protocol packets bytes start end action log-status').split()
MAX_BYTES = 20 * 1024 * 1024
MAX_COUNTER = 2**63 - 1
FLOW_COLUMNS = ['timestamp', 'start_time', 'end_time', 'src_ip', 'dst_ip',
                'src_port', 'dst_port', 'protocol', 'packets', 'bytes',
                'direction', 'interface_id', 'account_id', 'action',
                'crosses_windows', 'duration_seconds', 'origin',
                'source_file', 'source_line']


@dataclass
class ImportResult:
    flows: pd.DataFrame
    diagnostics: pd.DataFrame
    scope: list[str]
    interface_id: str
    window_policy: str

    @property
    def summary(self):
        return self.diagnostics.groupby('status').size().rename('lines').reset_index()


def decode_file(payload):
    if len(payload) > MAX_BYTES:
        raise ValueError('Fichier compressé ou texte supérieur à 20 Mio.')
    if payload.startswith(b'\x1f\x8b'):
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:
                payload = stream.read(MAX_BYTES + 1)
        except (OSError, EOFError, zlib.error) as exc:
            raise ValueError('Gzip illisible ou tronqué.') from exc
    if len(payload) > MAX_BYTES:
        raise ValueError('Fichier décompressé supérieur à 20 Mio.')
    try:
        return payload.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError('Texte UTF-8 attendu ; Parquet/JSON/CSV non pris en charge.') from exc


def unsigned(value, name, maximum=MAX_COUNTER):
    if not re.fullmatch(r'[0-9]+', value):
        raise ValueError(f'{name} absent ou entier non négatif invalide')
    number = int(value)
    if number > maximum:
        raise ValueError(f'{name} hors limites')
    return number


def import_files(files, lab_cidrs, interface_id, window_policy='exclude'):
    """files : liste de (nom, octets) ; dédoublonnage partagé entre ces fichiers.

    Sans en-tête : ordre AWS standard uniquement. Avec en-tête : les 14 champs
    standard sont requis, les champs supplémentaires sont conservés pour l'identité
    de dédoublonnage mais ne remplacent pas srcaddr/dstaddr (NAT non résolu).
    """
    if not lab_cidrs:
        raise ValueError('Définir explicitement au moins un CIDR du laboratoire.')
    try:
        networks = [ipaddress.ip_network(cidr.strip(), strict=True) for cidr in lab_cidrs]
    except ValueError as exc:
        raise ValueError('CIDR invalide : utiliser un réseau aligné, /32 pour un hôte IPv4, /128 pour IPv6.') from exc
    if any(network.prefixlen == 0 for network in networks):
        raise ValueError('Un périmètre /0 ne permet pas de définir le laboratoire.')
    if not re.fullmatch(r'eni-[a-zA-Z0-9]+', interface_id):
        raise ValueError('Indiquer une seule interface ENI du laboratoire (eni-…).')
    if window_policy not in ['exclude', 'end']:
        raise ValueError('Politique de fenêtre attendue : exclude ou end.')
    seen, rows, diagnostics = set(), [], []
    total_decoded = 0

    def diagnostic(name, line, status, reason, record=None):
        diagnostics.append(dict(source_file=name, source_line=line, status=status,
                                reason=reason, reported_bytes=(record or {}).get('bytes'),
                                reported_packets=(record or {}).get('packets')))

    def belongs(address):
        return any(address.version == network.version and address in network for network in networks)

    for name, payload in files:
        try:
            text = decode_file(payload)
        except ValueError as exc:
            diagnostic(name, 0, 'invalid_file', str(exc))
            continue
        total_decoded += len(text.encode('utf-8'))
        if total_decoded > 50 * 1024 * 1024:
            raise ValueError('Lot décompressé supérieur à 50 Mio : réduire le lot.')
        fields = DEFAULT_FIELDS
        for line_number, line in enumerate(text.splitlines(), start=1):
            values = line.split()
            if not values:
                continue
            if 'version' in values:
                if len(values) != len(set(values)) or not set(DEFAULT_FIELDS).issubset(values):
                    raise ValueError(f'{name}:{line_number} : en-tête incomplet ou dupliqué.')
                fields = values
                continue
            if len(values) != len(fields):
                diagnostic(name, line_number, 'invalid', f'{len(fields)} champs attendus, {len(values)} reçus')
                continue
            record = dict(zip(fields, values))
            # Identité exacte des champs présents, incluant ENI et métadonnées custom.
            identity = tuple(sorted(record.items()))
            if identity in seen:
                diagnostic(name, line_number, 'duplicate', 'Enregistrement exact déjà présent dans ce lot', record)
                continue
            seen.add(identity)
            if record['interface-id'] != interface_id:
                diagnostic(name, line_number, 'other_interface', 'ENI hors du point de collecte choisi', record)
                continue
            status = record['log-status']
            if status in ['NODATA', 'SKIPDATA']:
                diagnostic(name, line_number, status.lower(), 'État de collecte ; aucun volume imputé', record)
                continue
            try:
                if status != 'OK':
                    raise ValueError('log-status inconnu')
                version = unsigned(record['version'], 'version', 1000)
                if version < 2 or (fields == DEFAULT_FIELDS and version != 2):
                    raise ValueError('Version/format incompatible ; fournir un en-tête pour le custom')
                if record['action'] not in ['ACCEPT', 'REJECT']:
                    raise ValueError('action invalide')
                src, dst = ipaddress.ip_address(record['srcaddr']), ipaddress.ip_address(record['dstaddr'])
                if src.version != dst.version:
                    raise ValueError('Familles IP source/destination différentes')
                protocol = unsigned(record['protocol'], 'protocol', 255)
                packets = unsigned(record['packets'], 'packets')
                size = unsigned(record['bytes'], 'bytes')
                if packets == 0 and size > 0:
                    raise ValueError('Octets positifs avec zéro paquet')
                start = pd.Timestamp(unsigned(record['start'], 'start'), unit='s', tz='UTC')
                end = pd.Timestamp(unsigned(record['end'], 'end'), unit='s', tz='UTC')
                # Force une borne commune compatible avec les opérations pandas ns.
                start, end = start.as_unit('ns'), end.as_unit('ns')
                if end < start:
                    raise ValueError('end antérieur à start')
                if end > pd.Timestamp.now(tz='UTC') + pd.Timedelta(minutes=5):
                    raise ValueError('Horodatage futur de plus de cinq minutes')
                ports = [unsigned(record[k], k, 65535) for k in ['srcport', 'dstport']]
            except (ValueError, OverflowError, pd.errors.OutOfBoundsDatetime) as exc:
                diagnostic(name, line_number, 'invalid', str(exc), record)
                continue
            if record['action'] == 'REJECT':
                diagnostic(name, line_number, 'rejected_traffic', 'Trafic refusé conservé au diagnostic, pas assimilé à des octets transférés', record)
                continue
            if protocol not in [6, 17]:
                diagnostic(name, line_number, 'unsupported_protocol', 'Analyse des ports limitée à TCP/UDP', record)
                continue
            source_internal, destination_internal = belongs(src), belongs(dst)
            if source_internal == destination_internal:
                diagnostic(name, line_number, 'internal' if source_internal else 'outside',
                           'Deux hôtes du laboratoire' if source_internal else 'Aucun hôte du laboratoire', record)
                continue
            crosses = start.floor('5min') != end.floor('5min')
            if crosses and window_policy == 'exclude':
                diagnostic(name, line_number, 'cross_window_excluded', 'Répartition des octets entre fenêtres inconnue', record)
                continue
            rows.append(dict(timestamp=end, start_time=start, end_time=end,
                             src_ip=str(src), dst_ip=str(dst), src_port=ports[0], dst_port=ports[1],
                             protocol='TCP' if protocol == 6 else 'UDP', packets=packets,
                             bytes=size, direction='outbound' if source_internal else 'inbound',
                             interface_id=interface_id, account_id=record['account-id'],
                             action='ACCEPT', crosses_windows=crosses,
                             duration_seconds=int((end - start).total_seconds()),
                             origin='aws_manual_import', source_file=name, source_line=line_number))
            diagnostic(name, line_number, 'accepted_cross_window' if crosses else 'accepted',
                       'Affectation intégrale à la fenêtre de fin' if crosses else 'Intervalle contenu dans une fenêtre', record)
    # Éviter tout débordement silencieux des sommes int64 en aval.
    if sum(row['bytes'] for row in rows) > MAX_COUNTER or sum(row['packets'] for row in rows) > MAX_COUNTER:
        raise ValueError('Somme des compteurs hors limites int64 ; réduire le lot.')
    flows = pd.DataFrame(rows, columns=FLOW_COLUMNS)
    diag = pd.DataFrame(diagnostics, columns=['source_file', 'source_line', 'status',
                                             'reason', 'reported_bytes', 'reported_packets'])
    return ImportResult(flows, diag, [str(n) for n in networks], interface_id, window_policy)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', type=Path)
    parser.add_argument('--lab-cidr', action='append', required=True)
    parser.add_argument('--interface-id', required=True)
    parser.add_argument('--window-policy', choices=['exclude', 'end'], default='exclude')
    parser.add_argument('--output', type=Path, default=Path('reports/aws_manual'))
    args = parser.parse_args()
    result = import_files([(str(path), path.read_bytes()) for path in args.files],
                          args.lab_cidr, args.interface_id, args.window_policy)
    args.output.mkdir(parents=True, exist_ok=True)
    result.flows.to_csv(args.output / 'flows.csv', index=False)
    result.diagnostics.to_csv(args.output / 'diagnostics.csv', index=False)
    detect(result.flows).to_csv(args.output / 'rule_alerts.csv', index=False)
    metadata = dict(origin='aws_manual_import', lab_cidrs=result.scope,
                    interface_id=result.interface_id, window_policy=result.window_policy,
                    timestamp='end, Unix seconds -> UTC', labeled=False,
                    rules=dict(ports=20, bytes_out=50_000_000))
    (args.output / 'import_metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print('IMPORT AWS MANUEL — provenance déclarée, aucune évaluation de performance')
    print(result.summary.to_string(index=False))
    print(f'Octets retenus (entrants + sortants) : {sum(result.flows["bytes"])}')


if __name__ == '__main__':
    main()
