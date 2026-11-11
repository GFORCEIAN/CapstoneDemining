#!/usr/bin/env python3
"""Click the window, then hold up or down to run port 4 motor A.

Up is forward, down is backward, neither is stop. Same socket and
bytes as jog_port4a.py. Speed is sent again every 0.2 s so the air
side does not stop the motor while a key is held.
"""

import socket
import tkinter as tk

HOST = "10.31.101.203"  # ground Pi Ethernet. Hotspot is 192.168.3.1
PORT = 5765
SPEED = 10  # -127..127

ADDR = (4 << 4) | 0  # port 4, motor A
STOP = bytes([0x03])

up = False
down = False


def command():
    if up and not down:
        return bytes([0x01, ADDR, SPEED & 0xFF])
    if down and not up:
        return bytes([0x01, ADDR, (-SPEED) & 0xFF])
    return STOP


def main():
    sock = socket.create_connection((HOST, PORT), timeout=5)
    sock.settimeout(0.2)

    root = tk.Tk()
    root.title("port 4A")
    root.geometry("320x180")
    label = tk.Label(root, text="click here\nup forward\ndown backward")
    label.pack(expand=True)
    root.focus_force()

    def set_up(_event):
        global up
        up = True

    def clear_up(_event):
        global up
        up = False

    def set_down(_event):
        global down
        down = True

    def clear_down(_event):
        global down
        down = False

    root.bind("<KeyPress-Up>", set_up)
    root.bind("<KeyRelease-Up>", clear_up)
    root.bind("<KeyPress-Down>", set_down)
    root.bind("<KeyRelease-Down>", clear_down)

    def tick():
        try:
            sock.sendall(command())
        except OSError:
            root.destroy()
            return
        root.after(20, tick)

    def close():
        try:
            sock.sendall(STOP)
        except OSError:
            pass
        sock.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    tick()
    root.mainloop()


if __name__ == "__main__":
    main()
