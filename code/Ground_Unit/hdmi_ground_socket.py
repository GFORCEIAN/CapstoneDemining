#!/usr/bin/env python3
"""Ground socket for Ben's controller UI.

Listens on every interface, port 5765. Ethernet is 10.31.101.203.
The Pi's own hotspot is 192.168.3.1. Same bytes as protocol.h:

    0x00 PING
    0x01 SET_MOTOR  [addr] [speed]
    0x02 SET_ALL    [port] [speed]
    0x03 STOP_ALL

Each frame is carried as MAVLink DATA16 through OpenHD on localhost:5760.
The air bridge writes it to the MegaPi and returns the raw reply, usually OK.
"""

import select
import socket
import struct
import sys
import threading
import time

LISTEN = ("0.0.0.0", 5765)
OHD = ("127.0.0.1", 5760)
SYSID = 255
COMPID = 190

NEED = {0x00: 0, 0x01: 2, 0x02: 2, 0x03: 0}

CRC_EXTRA = {
    0: 50,
    169: 234,
    323: 78,
    324: 132,
}


def crc_accumulate(byte, crc):
    tmp = byte ^ (crc & 0xFF)
    tmp = (tmp ^ (tmp << 4)) & 0xFF
    return ((crc >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4)) & 0xFFFF


def crc_of(data, extra):
    crc = 0xFFFF
    for byte in data:
        crc = crc_accumulate(byte, crc)
    return crc_accumulate(extra, crc)


class Mav:
    def __init__(self):
        self.seq = 0
        self.buf = bytearray()

    def pack(self, msgid, payload):
        header = bytes([
            len(payload) & 0xFF, self.seq & 0xFF, SYSID, COMPID, msgid & 0xFF,
        ])
        self.seq = (self.seq + 1) & 0xFF
        body = header + payload
        return bytes([0xFE]) + body + struct.pack("<H", crc_of(body, CRC_EXTRA[msgid]))

    def feed(self, data):
        self.buf.extend(data)
        out = []
        while self.buf:
            if self.buf[0] not in (0xFD, 0xFE):
                del self.buf[0]
                continue
            magic = self.buf[0]
            if magic == 0xFD:
                if len(self.buf) < 12:
                    return out
                length = self.buf[1]
                frame = 12 + length + (13 if self.buf[2] & 0x01 else 0)
                if len(self.buf) < frame:
                    return out
                raw = bytes(self.buf[:frame])
                msgid = raw[7] | (raw[8] << 8) | (raw[9] << 16)
                body = raw[1:10 + length]
                crc_at = 10 + length
                sysid, payload = raw[5], raw[10:10 + length]
            else:
                if len(self.buf) < 8:
                    return out
                length = self.buf[1]
                frame = 8 + length
                if len(self.buf) < frame:
                    return out
                raw = bytes(self.buf[:frame])
                msgid = raw[5]
                body = raw[1:6 + length]
                crc_at = 6 + length
                sysid, payload = raw[3], raw[6:6 + length]
            extra = CRC_EXTRA.get(msgid)
            if extra is None:
                del self.buf[0]
                continue
            got = struct.unpack_from("<H", raw, crc_at)[0]
            if crc_of(body, extra) != got:
                del self.buf[0]
                continue
            del self.buf[:frame]
            out.append((sysid, msgid, payload))
        return out


def data16(mav, blob):
    blob = bytes(blob[:16])
    return mav.pack(169, bytes([1, len(blob)]) + blob.ljust(16, b"\x00"))


def heartbeat(mav):
    return mav.pack(0, struct.pack("<IBBBBB", 0, 6, 0, 1, 4, 3))


class Frames:
    def __init__(self):
        self.buf = bytearray()

    def feed(self, data):
        self.buf.extend(data)
        out = []
        while self.buf:
            need = NEED.get(self.buf[0])
            if need is None:
                del self.buf[0]
                continue
            if len(self.buf) < 1 + need:
                break
            out.append(bytes(self.buf[:1 + need]))
            del self.buf[:1 + need]
        return out


def claim_air_uart():
    """Reopen the air FC UART onto /tmp/hdmi-fc.

    OpenHD does not reopen a path it already has saved. Set the GPIO UART,
    then the pty, so the air bridge is attached after a reboot.
    """
    def pack_set(seq, value):
        param_id = b"FC_UART_CONN".ljust(16, b"\x00")
        param_value = value.encode().ljust(128, b"\x00")
        payload = bytes([101, 191]) + param_id + param_value + bytes([11])
        header = bytes([
            len(payload) & 0xFF, 0, 0, seq & 0xFF, SYSID, COMPID,
            323 & 0xFF, (323 >> 8) & 0xFF, 0,
        ])
        body = header + payload
        return bytes([0xFD]) + body + struct.pack("<H", crc_of(body, CRC_EXTRA[323]))

    def once(value, seq):
        try:
            sock = socket.create_connection(OHD, timeout=2)
        except OSError as exc:
            print("UART claim waiting:", exc, flush=True)
            return None
        sock.settimeout(1.5)
        parser = Mav()
        try:
            sock.sendall(pack_set(seq, value))
            deadline = time.time() + 1.5
            while time.time() < deadline:
                try:
                    chunk = sock.recv(2048)
                except socket.timeout:
                    break
                if not chunk:
                    break
                for _sysid, msgid, body in parser.feed(chunk):
                    if msgid != 324:
                        continue
                    body = body.ljust(146, b"\x00")
                    stored = body[16:].split(b"\x00", 1)[0]
                    if stored == value.encode():
                        return body[145]
        except OSError as exc:
            print("UART claim failed:", exc, flush=True)
        finally:
            sock.close()
        return None

    seq = 0
    while True:
        cleared = once("/dev/serial0", seq)
        seq = (seq + 1) & 0xFF
        claimed = once("/tmp/hdmi-fc", seq)
        seq = (seq + 1) & 0xFF
        if claimed == 0:
            print("air UART claimed /tmp/hdmi-fc", flush=True)
            return
        print("air UART claim result", claimed, "after", cleared, flush=True)
        time.sleep(5)


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(LISTEN)
    server.listen(1)
    server.setblocking(False)
    print("listening %s:%d" % LISTEN, flush=True)
    threading.Thread(target=claim_air_uart, daemon=True).start()

    mav_sock = None
    mav = Mav()
    parser = Mav()
    client = None
    frames = Frames()
    last_beat = 0.0

    def drop_client():
        nonlocal client, frames
        if client is not None:
            try:
                client.close()
            except OSError:
                pass
        client = None
        frames = Frames()

    def ensure_mav():
        nonlocal mav_sock, parser
        if mav_sock is not None:
            return True
        try:
            mav_sock = socket.create_connection(OHD, timeout=2)
            mav_sock.setblocking(False)
            parser = Mav()
            print("OpenHD uplink up", flush=True)
            return True
        except OSError as exc:
            mav_sock = None
            print("OpenHD uplink waiting:", exc, flush=True)
            return False

    while True:
        now = time.time()
        if mav_sock is None:
            ensure_mav()
        if mav_sock is not None and now - last_beat >= 1.0:
            try:
                mav_sock.sendall(heartbeat(mav))
                last_beat = now
            except OSError:
                mav_sock.close()
                mav_sock = None

        watch = [server]
        if client is not None:
            watch.append(client)
        if mav_sock is not None:
            watch.append(mav_sock)
        ready, _, _ = select.select(watch, [], [], 0.5)

        if server in ready:
            try:
                new_client, addr = server.accept()
            except OSError:
                new_client = None
            if new_client is not None:
                drop_client()
                new_client.setblocking(False)
                client = new_client
                print("UI connected", addr, flush=True)
                if mav_sock is not None:
                    try:
                        mav_sock.sendall(data16(mav, bytes([0x03])))
                    except OSError:
                        mav_sock.close()
                        mav_sock = None

        if client is not None and client in ready:
            try:
                chunk = client.recv(256)
            except OSError:
                chunk = b""
            if not chunk:
                print("UI disconnected", flush=True)
                drop_client()
                if mav_sock is not None:
                    try:
                        mav_sock.sendall(data16(mav, bytes([0x03])))
                    except OSError:
                        mav_sock.close()
                        mav_sock = None
            elif mav_sock is not None:
                for frame in frames.feed(chunk):
                    try:
                        mav_sock.sendall(data16(mav, frame))
                    except OSError:
                        mav_sock.close()
                        mav_sock = None
                        break

        if mav_sock is not None and mav_sock in ready:
            try:
                chunk = mav_sock.recv(2048)
            except OSError:
                chunk = b""
            if not chunk:
                mav_sock.close()
                mav_sock = None
                continue
            for sysid, msgid, payload in parser.feed(chunk):
                if msgid != 169 or sysid != 1 or len(payload) < 2 or client is None:
                    continue
                n = payload[1]
                reply = payload[2:2 + n]
                if not reply:
                    continue
                try:
                    client.sendall(reply)
                except OSError:
                    drop_client()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
