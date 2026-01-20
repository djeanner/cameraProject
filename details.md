## Details of Configuration (`config.json`)

### Camera parameters (`camera`)
- `codec`: `'rgb'` (or `'h264'` if supported)  
- `framerate`: Capture frames per second  
- `height`, `width`: Resolution in pixels  
- `video_mode`: `'stream'` for continuous video, `'still'` for single image captures  

### Export settings (`export`)
- `auto_save_interval_s`: Interval in seconds for automatic saves (e.g., 900 = 15 minutes)  
- `auto_save_use_ring`: `true`/`false` — whether to use the ring buffer for auto-save  
- `base_dir`: Directory to save frames (e.g., `"./captures"`)  
- `formats`: List of formats to save, e.g., `['jpg', 'png', 'npy']`  
- `save_before_s`: Seconds of frames to save before and after a trigger  
- `stack_dark_frames`: Whether to stack multiple frames to improve low-light images  
- `stack_count`: Number of frames to stack  

### Logging settings (`logging`)
- `level`: Logging verbosity (e.g., `'INFO'`, `'DEBUG'`)  

### MJPEG server settings (`mjpeg_server`)
- `enable`: `true`/`false` — enable MJPEG streaming server  
- `fps`: Frames per second for MJPEG stream  
- `port`: TCP port for MJPEG stream (e.g., `8080`)  

### Network configuration (`network`)
- `trigger_port`: TCP port for external triggers (e.g., `9999`)  

### Night mode parameters (`night`)
- `enable`: Enable or disable night mode  
- `dark_threshold`: Frame dark score below which the system considers it night  
- `bright_threshold`: Frame brightness above which the system exits night mode  
- `min_dark_frames`: Number of consecutive dark frames needed to enter night mode  
- `mode`: `'still'` or `'slow_video'` — camera behavior in night mode  
- `exposure_us`: Camera exposure time in microseconds during night mode  
- `gain`: Camera gain (ISO equivalent) during night mode  

### Ring buffer settings (`ring`)
- `size`: Number of frames to store in memory (effective size auto-adjusted based on available RAM, image resolution, and format)  
- `downscale`: Optional reduction of image resolution for the ring buffer
  - `enable`: `true`/`false` — if false, full-res frames are stored  
  - `width`, `height`: dimensions for downscaled frames  

> Adjusting these parameters allows full control over the camera, night mode logic, image saving, external triggers, and MJPEG streaming.
