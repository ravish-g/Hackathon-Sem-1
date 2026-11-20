# Vision worker

The process-feeds worker runs two independent OpenCV capture threads and two
independent bounded inference workers. It requires real YOLO weights and real
footage for measured results.

Required runtime dependencies:

- `opencv-python`
- `numpy`
- `ultralytics>=8.3`
- `supervision>=0.27`
- `trackers` for optional supported tracking
- `requests` for HTTPS telemetry publishing

These packages are integration requirements and are not added to the Django
root requirements file. Real detection cannot run until they are installed and
a YOLO checkpoint is available.

The Ultralytics YOLO model is instantiated separately for each feed. This avoids
sharing an inference runtime concurrently across the two processor threads.
Trackers and zone state also remain per-feed.

Run with two MP4 sources:

```powershell
python -m vision.main --feed feed-a=clip-a.mp4 --feed feed-b=clip-b.mp4 --model yolo11n.pt --device cpu --frame-stride 1 --telemetry-url http://127.0.0.1:8000/internal/telemetry/ --worker-token <token>
```

Camera sources use numeric indices or RTSP URLs as the source value, for example
`--feed feed-a=0 --feed feed-b=1`.

`--resolution WIDTHxHEIGHT` resizes every captured frame before inference.
For example, `--resolution 1280x720`. Invalid or non-positive resolutions are
rejected by the CLI.

Each calibration JSON may contain `image_points`, `ground_points_m`,
`calibration_version`, and zone polygons:

```json
{
  "image_points": [[0, 0], [100, 0], [100, 100], [0, 100]],
  "ground_points_m": [[0, 0], [10, 0], [10, 10], [0, 10]],
  "calibration_version": 1,
  "zones": [
    {
      "zone_id": "entrance",
      "ground_polygon_m": [[0, 0], [10, 0], [10, 10], [0, 10]]
    }
  ]
}
```

Pass each file with `--calibration feed-a=feed-a.json`.
An absent or invalid calibration always produces `is_valid=false`,
`density_people_per_m2=null`, and `calibration_invalid`.
