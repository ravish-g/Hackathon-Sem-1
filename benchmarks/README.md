# Crowd counting measurements

## Offline benchmark

Real clips are not included in this repository. The benchmark is runnable but
reports `unmeasured` until a real ground-truth CSV and prediction CSV are supplied.

CSV files use `feed_id`, `frame_id`, and one count column:

- ground truth: `people_count`
- predictions: `predicted_count`

```powershell
python benchmarks/benchmark.py --ground-truth ground_truth.csv --predictions predictions.csv
```

The JSON result reports absolute error, nonzero-frame mean absolute percentage
error, explicit zero-count frames, and optional measured FPS strings. It does
not claim accuracy or performance until real footage and manual labels exist.

### Dense-crowd detector comparison

On the development CPU, YOLO11n at confidence 0.25 produced these person
detections at the start, midpoint and 90% mark of two project uploads.
The worker uses a whole-frame pass plus overlapping 640-pixel crops by
default. Set VISION_TILE_SIZE=0 in Compose to use a whole-frame pass alone.

| Upload prefix and source resolution | Whole frame | Whole frame plus crops | Tiled inference seconds per sampled frame |
| --- | --- | --- | --- |
| 5fb0, 1920x1080 | 5, 6, 4 | 43, 40, 40 | 0.69, 0.51, 0.51 |
| 667e, 2560x1440 | 3, 4, 9 | 119, 108, 111 | 0.91, 0.91, 0.92 |

Each pair used the same decoded frame. Timings include detection and merging
on one feed at a time. Ground-truth counts remain unmeasured.


### Concurrent Docker replay

On 21 November 2026 the Docker CPU worker processed the north and south
uploads concurrently on an Intel Core i5-12500H with YOLO11n and 640-pixel
tiles. A 60-second window of stored observations, grouped by feed and
processing timestamp, gave the following application-level throughput.

| Feed | Samples delivered | Delivered frames/s | Mean processing latency | Peak processing latency |
| --- | ---: | ---: | ---: | ---: |
| North | 21 | 0.35 | 2929 ms | 5055 ms |
| South | 38 | 0.63 | 1618 ms | 3542 ms |

Both feeds were active during this observation. The 5 FPS per-feed target
was missed on this CPU. Timing includes the shared detector and contention
between the two feeds.

### Network input

A separate local test replayed a project clip through FFmpeg and MediaMTX as
an H.264 RTSP/TCP stream at 1280 × 720 and 8 input FPS. A new network feed
delivered a JPEG preview (HTTP 200) and sequenced person detections, including
31 people at sample 4. This verifies the RTSP ingestion path using a controlled
source. Physical camera connectivity and count accuracy depend on the venue.

The same temporary RTSP feed then received a test calibration through the
normal API. Subsequent stored samples contained zone counts, the new
calibration version and density. The dashboard returned a density history.
The dimensions used in this functional check were synthetic.
