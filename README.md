# cameraProject
Python project for camera control
pi_cam_service.zip

trigger event to save images with  
```bash
echo SNAP | nc raspberrypi 9999
```

# Pi Cam Service (Python 3.11) Manual

## Overview

This project is a Python 3.11-based Pi camera service designed for continuous video streaming, night mode, ring buffer capture, and flexible image export. The system is modular and allows integration with external triggers or object detection processes.

## Project Structure

| File                   | Purpose                                                                                               |
| ---------------------- | ----------------------------------------------------------------------------------------------------- |
| `config.json`          | JSON configuration for camera, ring buffer, night mode, export options, network trigger, and logging. |
| `ring_buffer.py`       | Thread-safe ring buffer storing recent frames along with metadata.                                    |
| `metadata.py`          | `FrameMetadata` dataclass storing frame ID, timestamp, dark score, and night mode flag.               |
| `night_mode.py`        | Controller that determines when to enter or exit night mode based on brightness analysis.             |
| `exporter.py`          | Handles saving frames in multiple formats and optionally stacks dark frames before saving.            |
| `trigger_server.py`    | Network-based trigger server to save recent frames on-demand.                                         |
| `camera_controller.py` | Controls PiCamera2 for continuous video capture, feeding frames into the ring buffer.                 |
| `main.py`              | Orchestrates camera, night mode controller, ring buffer, exporter, and trigger server.                |
| `requirements.txt`     | Lists required Python packages: `picamera2`, `numpy`, `opencv-python`                                 |

## Installation

1. Clone or download the project.
2. Install Python 3.11 if not already installed.
3. Create a virtual environment (optional but recommended except on weak system):

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Configuration (`config.json`)

* `camera`: Camera parameters

  * `width`, `height`: Resolution
  * `framerate`: Capture FPS
  * `codec`: 'rgb' (or h264, if supported)
  * `video_mode`: 'stream' or 'still'
* `ring`: Ring buffer size (number of frames)
* `night`: Night mode parameters

  * `enable`: Enable night mode logic
  * `dark_threshold`: Frame dark score to consider dark
  * `bright_threshold`: Score to exit night mode
  * `min_dark_frames`: Number of consecutive dark frames to enter night mode
  * `mode`: 'still' or 'slow_video'
  * `exposure_us`, `gain`: Camera exposure and gain during night mode
* `export`: Image export settings

  * `base_dir`: Directory to save frames
  * `formats`: List of formats ['jpg', 'png', 'npy']
  * `save_before_s`, `save_after_s`: Seconds of frames to save before/after trigger
  * `stack_dark_frames`: Whether to stack multiple frames for low-light enhancement
  * `stack_count`: Number of frames to stack
* `network`: Trigger server port
* `logging`: Logging level

## Usage

1. Start the main service:

   ```bash
   python3 main.py
   ```
2. The service continuously captures frames into the ring buffer.
3. Night mode automatically triggers based on brightness.
4. External systems can send network triggers to save recent frames.

## Triggering Image Capture

Send a string command to the trigger port (default 9999) via TCP. This will save the last N seconds of frames according to the `export` configuration.

Example using `nc` (netcat):

```bash
echo "save" | nc <pi_ip> 9999
```

## Notes

* The ring buffer keeps the most recent frames for on-demand saving.
* The night mode controller only triggers when consecutive frames are below the dark threshold.
* Exporter supports stacking frames to improve image brightness for low-light captures.
* Images are timestamped and numbered to maintain order.
* This project is optimized for Python 3.11 features like type hints, `match/case`, and `dataclasses(kw_only=True)`.


