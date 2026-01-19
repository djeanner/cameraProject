#!/usr/bin/env python3
import socket
import struct
import time
import os

HOST = "raspberrypi"  # Replace with your Pi's hostname or IP
PORT = 9999
MAX_FRAMES = 10  # number of frames to request

SAVE_DIR = "received_frames"
os.makedirs(SAVE_DIR, exist_ok=True)

def recv_all(sock, n):
    """Receive exactly n bytes from the socket"""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None  # connection closed
        buf += chunk
    return buf

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    cmd = f"shortstream {MAX_FRAMES}\n"
    s.sendall(cmd.encode())

    frame_idx = 0
    while True:
        # Read 4-byte length prefix
        data = recv_all(s, 4)
        if not data:
            print("End of stream or connection closed")
            break
        size = struct.unpack(">I", data)[0]

        if size == 0:
            print("End of stream marker received")
            break  # no more images

        # Read the image data
        img_data = recv_all(s, size)
        if img_data is None:
            print("Connection closed before full image received")
            break

        # Save the image
        ts = time.time()
        filename = os.path.join(SAVE_DIR, f"frame_{frame_idx}_{int(ts*1000)}.jpg")
        with open(filename, "wb") as f:
            f.write(img_data)
        print(f"Saved {filename}")
        frame_idx += 1

print("All frames received")
