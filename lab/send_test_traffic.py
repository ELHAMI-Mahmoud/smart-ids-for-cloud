"""Trois essais bornés vers une cible privée de laboratoire ; bibliothèque standard uniquement."""
import argparse
from datetime import datetime, timezone
import ipaddress
import json
import socket


def private_target(value):
    address = ipaddress.ip_address(value)
    networks = ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '127.0.0.0/8']
    if address.version != 4 or not any(address in ipaddress.ip_network(n) for n in networks):
        raise argparse.ArgumentTypeError('Indiquer une IPv4 privée du laboratoire.')
    return str(address)


def transfer(target, port, size):
    with socket.create_connection((target, port), timeout=10) as connection:
        remaining = size
        block = b'0' * 65536
        while remaining:
            part = block[:min(remaining, len(block))]
            connection.sendall(part)
            remaining -= len(part)
        connection.shutdown(socket.SHUT_WR)
        reply = b''
        while True:
            chunk = connection.recv(100)
            if not chunk:
                break
            reply += chunk
        if reply.decode() != str(size):
            raise ValueError('Le récepteur ne confirme pas le volume attendu.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, type=private_target)
    parser.add_argument('--scenario', required=True, choices=['normal', 'scan', 'volume'])
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    if not 1 <= args.port <= 65516:
        parser.error('Port de départ attendu entre 1 et 65 516.')
    started = datetime.now(timezone.utc).isoformat()
    size, attempted = 0, []
    if args.scenario == 'scan':
        for port in range(args.port, args.port + 20):
            with socket.socket() as connection:
                connection.settimeout(1)
                code = connection.connect_ex((args.target, port))
                attempted.append(dict(port=port, connect_result=code))
    else:
        size = 1024 if args.scenario == 'normal' else 80 * 1024 * 1024
        transfer(args.target, args.port, size)
    print(json.dumps(dict(scenario=args.scenario, started_utc=started,
                          ended_utc=datetime.now(timezone.utc).isoformat(), target=args.target,
                          application_bytes_sent=size, attempts=attempted,
                          note='Essai volontaire du laboratoire ; ne constitue pas une mesure IDS.'), indent=2))


if __name__ == '__main__':
    main()
