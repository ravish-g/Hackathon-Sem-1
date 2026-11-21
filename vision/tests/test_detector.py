import numpy as np

from vision.detector import YoloPersonDetector


def test_dense_frame_merges_views_in_source_coordinates():
    detector = YoloPersonDetector.__new__(YoloPersonDetector)
    detector.tile_size = 640
    # A full-frame detection also appears in both overlapping tiles.
    common = [500, 50, 520, 100, .9, 0]
    distant_people = [[680 + i % 20 * 12, i // 20 * 20, 686 + i % 20 * 12,
                       i // 20 * 20 + 12, .8, 0] for i in range(200)]
    right = np.array([common, *distant_people], dtype=np.float32)
    right[:, [0, 2]] -= 360
    predictions = iter([np.array([common]), np.array([common]), right])
    detector._boxes = lambda frame: next(predictions)
    detected = detector.detect(np.zeros((320, 1000, 3), dtype=np.uint8))
    assert detected.count == 201
    assert set(detected.xyxy[:, 0]) == {500, *(row[0] for row in distant_people)}
