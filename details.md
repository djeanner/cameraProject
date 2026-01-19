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