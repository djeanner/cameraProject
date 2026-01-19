import socket

HOST = "raspberrypi"
PORT = 8080

s = socket.create_connection((HOST, PORT))
s.sendall(b"GET /stream HTTP/1.1\r\nHost: raspberrypi\r\n\r\n")
f = s.makefile("rb")

print("Connected, waiting for frames...")

while True:
    line = f.readline()
    if not line:
        print("Connection closed by server")
        break

    if line.startswith(b"--frame"):
        headers = {}
        while True:
            line = f.readline().strip()
            if not line:
                break
            if b":" in line:
                key, value = line.decode().split(":", 1)
                headers[key.strip()] = value.strip()

        if "Content-Length" not in headers:
            continue

        length = int(headers["Content-Length"])
        jpeg = f.read(length)  # ✅ read exactly the frame data in binary

        # parse metadata
        frame_id = int(headers.get("X-Frame-Id", 0))
        ts = float(headers.get("X-Timestamp", 0))
        dark_score = float(headers.get("X-Dark-Score", 0))
        night = bool(int(headers.get("X-Night", 0)))

        print(f"Frame {frame_id}, Night={night}, Dark score={dark_score:.1f}, Timestamp={ts:.3f}")

    else:
        print(f"Skipping: {line}")
        continue


