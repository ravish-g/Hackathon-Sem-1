import argparse
import json
import time
from pathlib import Path

import numpy as np

from .calibration import HomographyCalibration
from .detector import YoloPersonDetector
from .publisher import TelemetryPublisher
from .scheduler import SourceProcessor
from .sources import SourceReader
from .zones import Zone


def load_feed_config(path: str | None) -> tuple[HomographyCalibration | None, list[Zone]]:
    if not path:
        return None, []
    config_path = Path(path)
    if not config_path.is_file():
        raise ValueError(f"calibration config does not exist: {path}")
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    calibration = None
    if "image_points" in config and "ground_points_m" in config:
        calibration = HomographyCalibration(
            image_points=np.asarray(config["image_points"], dtype=np.float32),
            ground_points_m=np.asarray(config["ground_points_m"], dtype=np.float32),
            version=int(config.get("calibration_version", 1)),
        )
        if not calibration.valid:
            raise ValueError("invalid homography calibration")
    zones = [
        Zone(
            zone_id=item["zone_id"],
            ground_polygon_m=np.asarray(item["ground_polygon_m"], dtype=np.float32),
            image_polygon=np.asarray(item["image_polygon"], dtype=np.float32)
            if item.get("image_polygon") is not None
            else None,
        )
        for item in config.get("zones", [])
    ]
    return calibration, zones


class DualSourceWorker:
    def __init__(self, source_specs, calibration_paths, detector_factory, telemetry_url,
                 worker_token, frame_stride, frame_pacing_seconds, tracking,
                 target_resolution):
        if len(source_specs) != 2:
            raise ValueError("exactly two distinct source specifications are required")
        if len({feed_id for feed_id, _ in source_specs}) != 2:
            raise ValueError("feed IDs must be distinct")
        self.publisher = TelemetryPublisher(telemetry_url, worker_token)
        self.readers = []
        self.processors = []
        self.detectors = {}
        for feed_id, source in source_specs:
            calibration, zones = load_feed_config(calibration_paths.get(feed_id))
            detector = detector_factory(feed_id)
            self.detectors[feed_id] = detector
            processor = SourceProcessor(
                feed_id, detector, zones, calibration, self.publisher,
                queue_size=4,
                tracking=tracking,
                frame_pacing_seconds=frame_pacing_seconds,
            )
            reader = SourceReader(
                feed_id,
                source,
                processor.frames,
                frame_stride=frame_stride,
                target_resolution=target_resolution,
            )
            self.processors.append(processor)
            self.readers.append(reader)

    def run(self) -> None:
        self.publisher.start()
        for processor in self.processors:
            processor.start()
        for reader in self.readers:
            reader.start()
        try:
            while any(reader.thread and reader.thread.is_alive() for reader in self.readers):
                time.sleep(0.25)
        finally:
            for reader in self.readers:
                reader.stop()
            for processor in self.processors:
                processor.stop()
            self.publisher.stop()


def split_specs(values):
    specs = []
    for value in values:
        if "=" not in value:
            raise ValueError("source must use FEED_ID=SOURCE")
        feed_id, source = value.split("=", 1)
        specs.append((feed_id, source))
    return specs


def split_paths(values):
    paths = {}
    for value in values:
        if "=" not in value:
            raise ValueError("calibration must use FEED_ID=JSON")
        feed_id, path = value.split("=", 1)
        paths[feed_id] = path
    return paths


def parse_resolution(value: str) -> tuple[int, int]:
    parts = value.lower().split("x")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("resolution must use WIDTHxHEIGHT, for example 1280x720")
    try:
        width, height = (int(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("resolution width and height must be integers") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("resolution width and height must be positive")
    return width, height


def parse_args():
    parser = argparse.ArgumentParser(description="Real two-feed crowd-density vision worker")
    parser.add_argument("--feed", action="append", required=True,
                        metavar="FEED_ID=SOURCE", help="two MP4 or camera sources")
    parser.add_argument("--calibration", action="append", default=[],
                        metavar="FEED_ID=JSON", help="per-feed homography and zones")
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--resolution", type=parse_resolution, default=(1280, 720),
                        metavar="WIDTHxHEIGHT",
                        help="resize each captured frame to WIDTHxHEIGHT before inference")
    parser.add_argument("--frame-pacing", type=float, default=0.0)
    parser.add_argument("--frame-stride", type=int, default=1)
    parser.add_argument("--telemetry-url")
    parser.add_argument("--worker-token")
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--tracking", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_specs = split_specs(args.feed)
    if len(source_specs) != 2:
        raise SystemExit("exactly two --feed FEED_ID=SOURCE arguments are required")
    detector_factory = lambda feed_id: YoloPersonDetector(
        args.model,
        args.confidence,
        args.device,
    )
    worker = DualSourceWorker(
        source_specs,
        split_paths(args.calibration),
        detector_factory,
        args.telemetry_url,
        args.worker_token,
        args.frame_stride,
        args.frame_pacing,
        args.tracking,
        args.resolution,
    )
    worker.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
