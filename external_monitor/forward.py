"""Opaque TLS forwarding to the LXC's current DHCP address, VPN interface only."""

import argparse
import ipaddress
import json
import select
import socket
import socketserver
import subprocess
import threading


class Forward(socketserver.BaseRequestHandler):
    def handle(self):
        with self.server.slots:
            result = subprocess.run(
                [
                    "pct",
                    "exec",
                    str(self.server.container),
                    "--",
                    "ip",
                    "-json",
                    "-4",
                    "addr",
                    "show",
                    "dev",
                    "eth0",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            addresses = [
                a["local"]
                for item in json.loads(result.stdout)
                for a in item["addr_info"]
                if a["scope"] == "global"
            ]
            target = str(ipaddress.IPv4Address(addresses[0]))
            with socket.create_connection(
                (target, self.server.server_address[1]), timeout=5
            ) as upstream:
                self.request.settimeout(10)
                sockets = (self.request, upstream)
                while True:
                    ready, _, _ = select.select(sockets, [], [], 20)
                    if not ready:
                        return
                    for source in ready:
                        data = source.recv(65536)
                        if not data:
                            return
                        (upstream if source is self.request else self.request).sendall(data)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bind", required=True)
    p.add_argument("--container", required=True, type=int)
    p.add_argument("--port", type=int, default=9443)
    a = p.parse_args()
    with Server((a.bind, a.port), Forward) as server:
        server.container = a.container
        server.slots = threading.BoundedSemaphore(16)
        server.serve_forever()


if __name__ == "__main__":
    main()
