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
