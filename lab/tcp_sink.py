"""Récepteur de données factices pour les deux VM de votre laboratoire."""
import argparse
from datetime import datetime, timezone
import json
import socketserver


class Sink(socketserver.BaseRequestHandler):
    def handle(self):
        count = 0
        self.request.settimeout(30)
        while True:
            block = self.request.recv(65536)
            if not block:
                break
            count += len(block)
        try:
            self.request.sendall(str(count).encode())
        except (BrokenPipeError, ConnectionResetError):
            pass  # Les sondes de ports peuvent fermer immédiatement la connexion.
        print(json.dumps(dict(time_utc=datetime.now(timezone.utc).isoformat(),
                              peer=self.client_address[0], application_bytes=count)), flush=True)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    with Server((args.bind, args.port), Sink) as server:
        print(f'Récepteur du laboratoire sur {args.bind}:{args.port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
