# cameraProject

Python camera control for low-RAM systems with ring buffer, day/night detection, night-frame stacking, and MJPEG streaming with metadata suitable for image or object analysis.

Python project for camera control written with assistance of AI. It is specifically designed for systems with little RAM. The ring buffer can be parametrized to reduce image size (allowing one to store more frames). It has two separate criteria for night and day detection based on brightness. Commands are accepted via a line-based TCP protocol (netcat) to save images, test system health, or query brightness for day/night status. The camera also supports MJPEG streaming including per-frame metadata, making the stream usable for object detection or other image analysis pipelines.

---

## Overview

Python 3.11-based Pi camera service for continuous video streaming, night mode, ring buffer, flexible image export, stacked low-light frames, and hourly auto-save.

---

## Project Structure

| File                   | Purpose |
|------------------------|---------|
| `config.json`          | Camera, ring buffer, night mode, export, network trigger, logging configuration |
| `ring_buffer.py`       | Thread-safe ring buffer with metadata |
| `metadata.py`          | `FrameMetadata` dataclass |
| `night_mode.py`        | Night mode controller based on brightness |
| `exporter.py`          | Save frames, optionally stack dark frames |
| `trigger_server.py`    | Network trigger server |
| `camera_controller.py` | PiCamera2 control, feeds ring buffer |
| `main.py`              | Orchestrates camera, night mode, ring buffer, exporter, triggers, and hourly auto-save |
| `stream_server.py`     | MJPEG server with frame metadata headers |
| `requirements.txt`     | `picamera2`, `numpy`, `opencv-python` |

---

## Installation

1. Clone or download the project.  
2. Install Python 3.11 if not already installed.  
3. (Optional) Create a virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
4. Install dependencies:
   ```bash
    pip install -r requirements.txt
   ```

## Configuration (config.json)

Central configuration for the Pi Cam Service:
* camera: width, height, framerate, codec, video_mode
* ring: size of ring buffer, optional downscale
* night: night mode enable, dark/bright thresholds, min dark frames, mode (still or slow_video), exposure/gain
* export: base_dir, formats, pre/post-trigger save seconds, stack_dark_frames, stack_count, auto_save_interval_s
* network: trigger TCP port
* logging: verbosity level

## Details of configuration (config.json)

* `camera`: Camera parameters
  * `width`, `height`: Resolution in pixels
  * `framerate`: Capture frames per second
  * `codec`: 'rgb' (or 'h264', if supported)
  * `video_mode`: 'stream' for continuous video, 'still' for single image captures
* `ring`: Requested number of frames (effective size auto-adjusted based on available RAM, image resolution, and format)
  * `size`: Number of frames to store in memory
  * `downscale`: Optional reduction of image resolution for ring buffer
    * `enable`: true/false — if false, full-res frames are stored
    * `width`,`height`: dimensions for downscaled frames
* `night`: Night mode parameters
  * `enable`: Enable or disable night mode
  * `dark_threshold`: Frame dark score below which the system considers it night
  * `bright_threshold`: Frame brightness above which the system exits night mode
  * `min_dark_frames`: Number of consecutive dark frames needed to enter night mode
  * `mode`: 'still' or 'slow_video', defining camera behavior in night mode
  * `exposure_us`: Camera exposure time in microseconds during night mode
  * `gain`: Camera gain (ISO equivalent) during night mode
* `export`: Image export settings
  * `base_dir`: Directory to save frames
  * `formats`: List of formats to save ['jpg', 'png', 'npy']
  * `save_before_s`: Seconds of frames to save before and after a trigger
  * `stack_dark_frames`: Whether to stack multiple frames to improve low-light images
  * `stack_count`: Number of frames to stack
  * `auto_save_interval_s`: Interval in seconds for automatic hourly (or custom) saves
* `network`: Trigger server configuration
  * `trigger_port`: TCP port for external triggers
* `logging`: Logging settings
  * `level`: Logging verbosity (e.g., 'INFO', 'DEBUG')
  Adjusting these allows full control of camera, night mode logic, image saving, and external triggers.
## Usage

### Start the service
```bash
cd pi_cam_service
python3 main.py
```

### External triggers (via netcat)

```bash
echo "save jpg" | nc raspberrypi 9999       # Capture a full-res frame
echo "pastStack jpg" | nc raspberrypi 9999  # Capture a stacked image from ring buffer
echo "night_level" | nc raspberrypi 9999    # Query night status
echo "health" | nc raspberrypi 9999         # Check system health
```

### Streaming

   On the client side MJPEG stream with metadata (frame ID, timestamp, dark score, night mode):
```bash
python3 client.py           # Continuous MJPEG client prints metadata per frame (port 10000)
python3 clientShortStream.py # Short-term stream saving frames to folder (blocks other triggers uses port 9999)
```
    VLC or a browser can connect directly to MJPEG (`http://raspberrypi:8080/stream`) and display live video. Switching between VLC and Python client works safely.

### Stream Port and Client Switching

The MJPEG stream runs on **port 8080**. Only one client can actively receive the stream at a time. If you are using VLC to visualize the stream, the Python MJPEG client (`client.py`) will not receive frames simultaneously. To switch:

1. Stop VLC before starting `client.py` to avoid connection refusal or stalls.
2. Start `client.py` to read the stream and print metadata per frame.
3. You can safely stop the Python client and restart VLC to resume visualization.  

This ensures smooth operation without losing triggers or metadata, while keeping the stream accessible for either analysis (Python client) or display (VLC).

## Night Mode and Stacking
* Night mode adjusts camera for low-light: increases exposure and gain, switches mode (still or slow_video).
* Only triggers after min_dark_frames consecutive dark frames to prevent flicker-induced false positives.
* stack_dark_frames combines multiple dark frames into a single averaged image, reducing noise similar to long-exposure photography.
* Metadata per frame (X-Frame-Id, X-Timestamp, X-Dark-Score, X-Night) is available in MJPEG stream for analysis or automated workflows.

## Auto-Save Behavior
* auto_save_interval_s periodically saves frames.
* Day mode: normal video frame.
* Night mode: long-exposure or stacked still frames.

## Notes

* Ring buffer stores recent frames efficiently.
* Stacking improves low-light image quality.
* Images are timestamped and numbered.
* Optimized for Python 3.11 features: type hints, match/case, dataclasses(kw_only=True).
* Full-res 1024×768 color images can require ~700MB RAM; downscale recommended on Pi 1B+ (~136MB available).

## Updating Python program
```bash
scp pi_cam_service_py311/* dan@raspberrypi://home/dan/pi_cam_service
```

## Retrieving Images
```bash
scp -rp dan@raspberrypi://home/dan/pi_cam_service/captures .
rsync -av --progress dan@raspberrypi:/home/dan/pi_cam_service/captures/ ./captures/
# Limit bandwidth (KB/s)
rsync -av --bwlimit=500 --progress dan@raspberrypi:/home/dan/pi_cam_service/captures/ ./captures/
```

This version reflects metadata streaming, night/day dual thresholds, and frame stacking, while keeping your original ring buffer, triggers, and low-RAM optimization.