#!/usr/bin/env python3
"""Air-side bridge. OpenHD's FC UART is a pty this process creates.
Ben's frames arrive as MAVLink DATA16 and go out the MegaPi USB port
as the binary protocol in protocol.h. Replies ("OK") go back the same way.

Speaks MAVLink 1 toward OpenHD. OpenHD drops MAVLink 2 replies.
"""

import os
import select
import socket
import struct
import sys
import termios
import time

USB = os.environ.get("HDMI_USB", "/dev/ttyUSB0")
LINK = "/tmp/hdmi-fc"
SYSID = 1
COMPID = 1
HALT_S = 1.0
POLL_S = 5.0
OHD_TCP = ("127.0.0.1", 5760)

CMD_PING = 0x00
CMD_SET_MOTOR = 0x01
CMD_SET_ALL = 0x02
CMD_STOP_ALL = 0x03
MOTION = (CMD_SET_MOTOR, CMD_SET_ALL)

MAV_CMD_COMPONENT_ARM_DISARM = 400
MAV_RESULT_ACCEPTED = 0
MAV_RESULT_FAILED = 4
MAV_TYPE_GROUND_ROVER = 10
MAV_AUTOPILOT_GENERIC = 0
MAV_STATE_STANDBY = 3
MAV_STATE_ACTIVE = 4
MAV_MODE_FLAG_CUSTOM_MODE_ENABLED = 1
MAV_MODE_FLAG_SAFETY_ARMED = 128
MAV_SEVERITY_INFO = 6
MAV_PARAM_EXT_TYPE_CUSTOM = 11

CRC_EXTRA = {
    0: 50,      # HEARTBEAT
    69: 243,    # MANUAL_CONTROL
    70: 124,    # RC_CHANNELS_OVERRIDE
    76: 152,    # COMMAND_LONG
    77: 143,    # COMMAND_ACK
    169: 234,   # DATA16
    253: 83,     # STATUSTEXT
    323: 78,     # PARAM_EXT_SET
    324: 132,    # PARAM_EXT_ACK
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
    def __init__(self, sysid, compid):
        self.sysid = sysid
        self.compid = compid
        self.seq = 0
        self.buf = bytearray()

    def pack(self, msgid, payload, version=1):
        if version == 2:
            header = bytes([
                len(payload) & 0xFF, 0, 0, self.seq & 0xFF,
                self.sysid, self.compid,
                msgid & 0xFF, (msgid >> 8) & 0xFF, (msgid >> 16) & 0xFF,
            ])
            magic = 0xFD
        else:
            header = bytes([
                len(payload) & 0xFF, self.seq & 0xFF,
                self.sysid, self.compid, msgid & 0xFF,
            ])
            magic = 0xFE
        self.seq = (self.seq + 1) & 0xFF
        body = header + payload
        crc = crc_of(body, CRC_EXTRA[msgid])
        return bytes([magic]) + body + struct.pack("<H", crc)

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
                sysid, compid, payload = raw[5], raw[6], raw[10:10 + length]
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
                sysid, compid, payload = raw[3], raw[4], raw[6:6 + length]
            extra = CRC_EXTRA.get(msgid)
            if extra is None:
                del self.buf[0]
                continue
            got = struct.unpack_from("<H", raw, crc_at)[0]
            if crc_of(body, extra) != got:
                del self.buf[0]
                continue
            del self.buf[:frame]
            out.append((sysid, compid, msgid, payload))
        return out


def heartbeat(mav, armed):
    mode = MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
    status = MAV_STATE_STANDBY
    if armed:
        mode |= MAV_MODE_FLAG_SAFETY_ARMED
        status = MAV_STATE_ACTIVE
    payload = struct.pack("<IBBBBB", 0, MAV_TYPE_GROUND_ROVER,
                          MAV_AUTOPILOT_GENERIC, mode, status, 3)
    return mav.pack(0, payload)


def command_ack(mav, command, result):
    return mav.pack(77, struct.pack("<HB", command, result))


def statustext(mav, text):
    raw = text.encode("ascii", "replace")[:50]
    return mav.pack(253, struct.pack("<B50s", MAV_SEVERITY_INFO, raw))


def data16(mav, blob):
    blob = bytes(blob[:16])
    payload = bytes([1, len(blob)]) + blob.ljust(16, b"\x00")
    return mav.pack(169, payload)


def configure_tty(fd):
    attr = termios.tcgetattr(fd)
    attr[0] = 0
    attr[1] = 0
    attr[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attr[3] = 0
    attr[4] = termios.B115200
    attr[5] = termios.B115200
    attr[6][termios.VMIN] = 0
    attr[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attr)


def usb_cmd(fd, payload, wait=0.4):
    termios.tcflush(fd, termios.TCIFLUSH)
    os.write(fd, payload)
    data = b""
    deadline = time.time() + wait
    while time.time() < deadline:
        ready, _, _ = select.select([fd], [], [], 0.05)
        if not ready:
            continue
        data += os.read(fd, 64)
        if b"OK" in data:
            break
    return data


def try_open_megapi():
    if not os.path.exists(USB):
        return None
    fd = None
    try:
        fd = os.open(USB, os.O_RDWR | os.O_NOCTTY)
        configure_tty(fd)
        # Opening the CH340 resets the Mega. Wait out the bootloader.
        time.sleep(2.2)
        termios.tcflush(fd, termios.TCIOFLUSH)
        reply = usb_cmd(fd, bytes([CMD_PING]))
        if b"OK" not in reply:
            os.close(fd)
            return None
        return fd
    except OSError:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        return None


def open_link():
    master, slave = os.openpty()
    slave_name = os.ttyname(slave)
    try:
        os.unlink(LINK)
    except FileNotFoundError:
        pass
    os.symlink(slave_name, LINK)
    os.chmod(slave_name, 0o666)
    # Hold the slave open so the pty survives until OpenHD opens it.
    return master, slave


def claim_fc_uart():
    """Point OpenHD's saved FC UART at our pty.

    A second write of the same path is rejected and does not reopen the
    port. Clear it, then set it, so setup_uart runs after the pty exists.
    """
    def send(value):
        param_id = b"FC_UART_CONN".ljust(16, b"\x00")
        param_value = value.encode().ljust(128, b"\x00")
        payload = bytes([101, 191]) + param_id + param_value + bytes([MAV_PARAM_EXT_TYPE_CUSTOM])
        talker = Mav(255, 190)
        frame = talker.pack(323, payload, version=2)
        try:
            sock = socket.create_connection(OHD_TCP, timeout=2)
        except OSError as exc:
            print("FC UART claim waiting:", exc, flush=True)
            return None
        sock.settimeout(1.5)
        parser = Mav(255, 190)
        result = None
        try:
            sock.sendall(frame)
            deadline = time.time() + 1.5
            while time.time() < deadline:
                try:
                    chunk = sock.recv(512)
                except socket.timeout:
                    break
                if not chunk:
                    break
                for _sysid, _compid, msgid, body in parser.feed(chunk):
                    if msgid != 324:
                        continue
                    body = body.ljust(146, b"\x00")
                    stored = body[16:].split(b"\x00", 1)[0]
                    if stored != value.encode():
                        continue
                    return body[145]
        except OSError as exc:
            print("FC UART claim failed:", exc, flush=True)
        finally:
            sock.close()
        return result

    cleared = send("/dev/serial0")
    if cleared != 0:
        print("FC UART clear result", cleared, flush=True)
        return False
    claimed = send(LINK)
    if claimed == 0:
        print("FC UART claimed", LINK, flush=True)
        return True
    print("FC UART claim result", claimed, flush=True)
    return False


def main():
    link, _slave = open_link()
    mav = Mav(SYSID, COMPID)
    parser = Mav(SYSID, COMPID)
    usb = None
    attempt = 0
    next_try = 0.0
    armed = False
    motors_live = False
    last_cmd = 0.0
    last_beat = 0.0
    uart_claimed = False
    next_claim = 0.0
    print("READY", LINK, flush=True)
    os.write(link, heartbeat(mav, False))

    while True:
        now = time.time()
        if usb is None and now >= next_try:
            opened = try_open_megapi()
            if opened is None:
                attempt += 1
                print("Trying to connect to MegaPi: Attempt %d" % attempt, flush=True)
                next_try = time.time() + POLL_S
            else:
                usb = opened
                attempt = 0
                print("MegaPi connected", flush=True)
                os.write(link, statustext(mav, "MegaPi connected"))
        if usb is not None and not os.path.exists(USB):
            try:
                os.close(usb)
            except OSError:
                pass
            usb = None
            motors_live = False
            next_try = 0
        if now - last_beat >= 1.0:
            try:
                os.write(link, heartbeat(mav, armed))
            except OSError:
                pass
            last_beat = now
        if motors_live and (now - last_cmd) > HALT_S:
            if usb is not None:
                try:
                    reply = usb_cmd(usb, bytes([CMD_STOP_ALL]))
                    print("HALT", reply, flush=True)
                except OSError:
                    os.close(usb)
                    usb = None
                    next_try = 0
            motors_live = False

        ready, _, _ = select.select([link], [], [], 0.1)
        if not ready:
            continue
        try:
            incoming = os.read(link, 512)
        except OSError:
            continue
        for _sysid, _compid, msgid, payload in parser.feed(incoming):
            if msgid == 169 and len(payload) >= 2:
                n = payload[1]
                frame = payload[2:2 + n]
                if not frame or usb is None:
                    continue
                try:
                    reply = usb_cmd(usb, frame)
                except OSError:
                    os.close(usb)
                    usb = None
                    motors_live = False
                    next_try = 0
                    continue
                last_cmd = time.time()
                if frame[0] in MOTION:
                    motors_live = True
                elif frame[0] == CMD_STOP_ALL:
                    motors_live = False
                if reply:
                    os.write(link, data16(mav, reply))
                continue
            if msgid in (69, 70):
                last_cmd = time.time()
                continue
            if msgid != 76:
                continue
            payload = payload.ljust(33, b"\x00")
            params = struct.unpack_from("<7f", payload)
            command, target, _tcomp, _confirm = struct.unpack_from("<HBBB", payload, 28)
            if target not in (0, SYSID) or command != MAV_CMD_COMPONENT_ARM_DISARM:
                continue
            if usb is None:
                os.write(link, command_ack(mav, command, MAV_RESULT_FAILED))
                continue
            reply = usb_cmd(usb, bytes([CMD_STOP_ALL]))
            ok = b"OK" in reply
            if ok:
                armed = params[0] >= 0.5
                motors_live = False
                last_cmd = time.time()
            os.write(link, command_ack(mav, command, MAV_RESULT_ACCEPTED if ok else MAV_RESULT_FAILED))
            text = ("armed" if armed else "disarmed") + " STOP_ALL " + reply.decode("ascii", "replace").strip()
            os.write(link, statustext(mav, text[:50]))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
