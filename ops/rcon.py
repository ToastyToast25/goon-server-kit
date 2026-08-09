#!/usr/bin/env python3
"""Minimal Source-RCON client for the Project Zomboid server.

Usage: rcon.py "command with args"
Reads host/port/password from goon-ops.conf next to this script, or defaults.
Resolves the game container's current IP at call time (it changes on recreation).
"""
import socket
import struct
import subprocess
import sys
import os

CONTAINER = "YOUR_CONTAINER_ID"
PORT = 27015
PASSWORD = "YOUR_RCON_PASSWORD"

SERVERDATA_AUTH = 3
SERVERDATA_EXECCOMMAND = 2


def container_ip():
    out = subprocess.run(
        ["docker", "inspect", CONTAINER, "--format",
         "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"],
        capture_output=True, text=True, timeout=10)
    ip = out.stdout.strip()
    if not ip:
        raise SystemExit("RCON: container has no IP (server down?)")
    return ip


def send_packet(sock, req_id, ptype, body):
    payload = struct.pack("<ii", req_id, ptype) + body.encode() + b"\x00\x00"
    sock.sendall(struct.pack("<i", len(payload)) + payload)


def recv_packet(sock):
    raw = b""
    while len(raw) < 4:
        chunk = sock.recv(4 - len(raw))
        if not chunk:
            raise SystemExit("RCON: connection closed")
        raw += chunk
    (length,) = struct.unpack("<i", raw)
    data = b""
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise SystemExit("RCON: connection closed mid-packet")
        data += chunk
    req_id, ptype = struct.unpack("<ii", data[:8])
    body = data[8:-2].decode(errors="replace")
    return req_id, ptype, body


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: rcon.py <command>")
    command = " ".join(sys.argv[1:])
    ip = container_ip()
    with socket.create_connection((ip, PORT), timeout=10) as sock:
        send_packet(sock, 1, SERVERDATA_AUTH, PASSWORD)
        req_id, ptype, _ = recv_packet(sock)
        if req_id == -1:
            raise SystemExit("RCON: auth failed")
        # some servers send an empty response value packet before the auth ack
        while ptype != 2:
            req_id, ptype, _ = recv_packet(sock)
            if req_id == -1:
                raise SystemExit("RCON: auth failed")
        send_packet(sock, 2, SERVERDATA_EXECCOMMAND, command)
        _, _, body = recv_packet(sock)
        print(body)


if __name__ == "__main__":
    main()
