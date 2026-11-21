Benchmark tooling belongs to the process-feeds workstream. No H7 performance result is claimed by the foundation.

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
on one feed at a time. Ground-truth counts and concurrent throughput remain
unmeasured.
