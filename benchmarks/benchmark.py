import argparse
import csv
import json
from pathlib import Path


def load_csv(path: str) -> dict[tuple[str, str], int]:
    values = {}
    with open(path, "r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            feed_id = str(row.get("feed_id") or row.get("source") or "")
            frame_id = str(row.get("frame_id") or row.get("timestamp") or "")
            count_key = "people_count" if "people_count" in row else "predicted_count"
            if count_key not in row:
                count_key = "count"
            values[(feed_id, frame_id)] = int(row[count_key])
    return values


def absolute_percentage_error(predicted: int, ground_truth: int) -> float:
    if ground_truth == 0:
        return 0.0 if predicted == 0 else 100.0
    return abs(predicted - ground_truth) / ground_truth * 100.0


def evaluate(ground_truth_path: str, prediction_path: str) -> dict:
    if not Path(ground_truth_path).is_file() or not Path(prediction_path).is_file():
        return {
            "status": "unmeasured",
            "reason": "real clips and manual ground truth/predictions were not supplied",
            "per_feed": {},
            "combined": {
                "frames": 0,
                "mean_absolute_error": None,
                "mean_absolute_percentage_error_nonzero": None,
                "zero_count_frames": None,
            },
        }
    truth = load_csv(ground_truth_path)
    predictions = load_csv(prediction_path)
    per_feed = {}
    all_errors = []
    zero_frames = 0
    for key, actual in truth.items():
        if key not in predictions:
            continue
        predicted = predictions[key]
        feed_id = key[0]
        bucket = per_feed.setdefault(feed_id, {
            "frames": 0,
            "absolute_errors": [],
            "zero_count_frames": 0,
            "percentage_errors": [],
        })
        absolute_error = abs(predicted - actual)
        bucket["frames"] += 1
        bucket["absolute_errors"].append(absolute_error)
        all_errors.append(absolute_error)
        if actual == 0:
            bucket["zero_count_frames"] += 1
            zero_frames += 1
        else:
            bucket["percentage_errors"].append(absolute_percentage_error(predicted, actual))
    per_feed_output = {}
    for feed_id, bucket in per_feed.items():
        errors = bucket["percentage_errors"]
        per_feed_output[feed_id] = {
            "frames": bucket["frames"],
            "mean_absolute_error": sum(bucket["absolute_errors"]) / len(bucket["absolute_errors"])
            if bucket["absolute_errors"] else None,
            "mean_absolute_percentage_error_nonzero": sum(errors) / len(errors) if errors else None,
            "zero_count_frames": bucket["zero_count_frames"],
        }
    nonzero_errors = [
        absolute_percentage_error(predictions[key], truth[key])
        for key in truth if key in predictions and truth[key] > 0
    ]
    return {
        "status": "measured" if per_feed_output else "unmeasured",
        "per_feed": per_feed_output,
        "combined": {
            "frames": len([key for key in truth if key in predictions]),
            "mean_absolute_error": sum(all_errors) / len(all_errors) if all_errors else None,
            "mean_absolute_percentage_error_nonzero": sum(nonzero_errors) / len(nonzero_errors)
            if nonzero_errors else None,
            "zero_count_frames": zero_frames,
        },
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Offline count and FPS benchmark")
    parser.add_argument("--ground-truth", default="")
    parser.add_argument("--predictions", default="")
    parser.add_argument("--per-feed-fps")
    parser.add_argument("--combined-fps")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = evaluate(args.ground_truth, args.predictions)
    if args.per_feed_fps:
        result["per_feed_fps"] = args.per_feed_fps
    if args.combined_fps:
        result["combined_fps"] = args.combined_fps
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
