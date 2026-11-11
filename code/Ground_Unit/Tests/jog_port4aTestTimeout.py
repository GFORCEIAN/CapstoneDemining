#!/usr/bin/env python3
"""Jog MegaPi port 4 motor A for 5 seconds, then stop.

Talks to the ground Pi socket. Same bytes as the MegaPi protocol.
The air side stops the motor if commands pause for a second, so this
sends the speed again every 0.2 s until the 5 seconds are up.

there should be noticable stopping with the motor since its supposed to stop the motor if its not receiving a steady stream of movement/control commands within a short enough time window.
"""

import socket
import time

HOST = "10.31.101.203"  # ground Pi Ethernet. Hotspot is 192.168.3.1
PORT = 5765
SPEED = 10  # -127..127
SECONDS = 5

ADDR = (4 << 4) | 0  # port 4, motor A
JOG = bytes([0x01, ADDR, SPEED & 0xFF])
STOP = bytes([0x03])


def main():
    sock = socket.create_connection((HOST, PORT), timeout=5)
    sock.settimeout(0.3)
    try:
        end = time.time() + SECONDS
        while time.time() < end:
            sock.sendall(JOG)
            time.sleep(1.2)
        sock.sendall(STOP)
    finally:
        try:
            sock.sendall(STOP)
        except OSError:
            pass
        sock.close()


if __name__ == "__main__":
    main()
