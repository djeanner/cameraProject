# cameraProject

Python project for camera control.


## Overview

Python 3.11-based Pi camera service for continuous video streaming, night mode, ring buffer, flexible image export, and hourly auto-save.

## Project Structure

| File                   | Purpose |
|------------------------|---------|
| `config.json`          | Camera, ring buffer, night mode, export, network trigger, logging configuration |
| `ring_buffer.py`       | Thread-safe ring buffer with metadata |
| `metadata.py`          | FrameMetadata dataclass |
| `night_mode.py`        | Night mode controller based on brightness |
| `exporter.py`          | Save frames, optionally stack dark frames |
| `trigger_server.py`    | Network trigger server |
| `camera_controller.py` | PiCamera2 control, feeds ring buffer |
| `main.py`              | Orchestrates camera, night mode, ring buffer, exporter, triggers, and hourly auto-save |
| `requirements.txt`     | `picamera2`, `numpy`, `opencv-python` |

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

The `config.json` file centralizes all configurable aspects of the Pi Cam Service. It includes:

* `camera`: Camera parameters
  * `width`, `height`: Resolution in pixels
  * `framerate`: Capture frames per second
  * `codec`: 'rgb' (or 'h264', if supported)
  * `video_mode`: 'stream' for continuous video, 'still' for single image captures
* `ring`: Ring buffer configuration
  * `size`: Number of frames to store in memory
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
  * `save_before_s`, `save_after_s`: Seconds of frames to save before and after a trigger
  * `stack_dark_frames`: Whether to stack multiple frames to improve low-light images
  * `stack_count`: Number of frames to stack
  * `auto_save_interval_s`: Interval in seconds for automatic hourly (or custom) saves
* `network`: Trigger server configuration
  * `trigger_port`: TCP port for external triggers
* `logging`: Logging settings
  * `level`: Logging verbosity (e.g., 'INFO', 'DEBUG')

Adjusting these values lets you control camera behavior, night mode logic, image saving preferences, and integration with external triggers without modifying Python code. This allows flexible adaptation to lighting conditions, storage requirements, and automated workflows.

## Usage

1. Start the service:
```bash
cd pi_cam_service
python3 main.py
```
2. Continuous capture to ring buffer.
3. Night mode auto-triggers.
4. External triggers (`echo "COMMAND" | nc <pi_ip> 9999`):

```bash
echo "save jpg" | nc raspberrypi 9999
echo "save png" | nc raspberrypi 9999
echo "night_level" | nc raspberrypi 9999  # Query night status
```

## Night Mode and Stacking

The night mode automatically adjusts the camera behavior when lighting conditions are low. Compared to normal daytime operation, night mode can:

* Increase exposure time (`exposure_us`) and sensor gain (`gain`) to capture brighter images in dark conditions.
* Switch the camera mode to `'still'` or `'slow_video'` to allow longer exposures without dropping frames.
* Trigger only after a configurable number of consecutive dark frames (`min_dark_frames`) to avoid false positives during brief shadows or flickers.

The `stack_dark_frames` option in the exporter further enhances low-light images. When enabled, it combines (`stacks`) multiple consecutive frames into a single image, averaging pixel values. This reduces noise and improves visibility while preserving details, similar to long-exposure photography, without increasing the actual exposure time of each frame.

## Notes

* Ring buffer stores recent frames.
* Stacking improves low-light images.
* Images timestamped and numbered.
* Optimized for Python 3.11 features: type hints, match/case, dataclasses(kw_only=True).

## Night Mode and Stacking

The night mode automatically adjusts the camera behavior when lighting conditions are low. Compared to normal daytime operation, night mode can:

* Increase exposure time (`exposure_us`) and sensor gain (`gain`) to capture brighter images in dark conditions.
* Switch the camera mode to `'still'` or `'slow_video'` depending on configuration, allowing longer exposures without dropping frames.
* When switching modes, the service logs exactly which camera parameters changed (mode, framerate, exposure, gain), helping with monitoring and debugging.
* Trigger only after a configurable number of consecutive dark frames (`min_dark_frames`) to avoid false positives during brief shadows or flickers.

The `stack_dark_frames` option in the exporter further enhances low-light images. When enabled, it combines (`stacks`) multiple consecutive frames into a single image, averaging pixel values. This reduces noise and improves visibility while preserving details, similar to long-exposure photography, without increasing the actual exposure time of each frame.

### Auto-Save Behavior

* The automatic save interval (`auto_save_interval_s`) periodically saves the most recent frame.
  - If the camera is in day mode, a normal video frame is saved.
  - If the camera is in night mode, the save captures the long-exposure still frame.


## Update python program

   ```bash
   scp pi_cam_service_py311/* dan@raspberrypi://home/dan/pi_cam_service
   ```

## get image folder

   ```bash
   scp -rp dan@raspberrypi://home/dan/pi_cam_service/captures .

   rsync -av --progress dan@raspberrypi:/home/dan/pi_cam_service/captures/ ./captures/
   echo "limit bandwidth in KB/s"
   rsync -av --bwlimit=500 --progress dan@raspberrypi:/home/dan/pi_cam_service/captures/ ./captures/
   ```