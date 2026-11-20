import threading
import time
import uuid
from datetime import datetime, timezone
from queue import Empty, Full, Queue
from pathlib import Path

import cv2

from .types import FramePacket


class SourceReader:
    def __init__(self, feed_id: str, source, frames: Queue, frame_stride: int = 1,
                 reconnect_delay: float = 2.0, target_resolution: tuple[int, int] | None = None):
        self.feed_id = feed_id
        self.source = source
        self.frames = frames
        self.frame_stride = max(1, frame_stride)
        self.reconnect_delay = reconnect_delay
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.frame_number = 0
        self.target_resolution = target_resolution
        self.ended = False

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name=f"capture-{self.feed_id}", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3.0)

    def _run(self) -> None:
        while not self.stop_event.is_set():
            capture = cv2.VideoCapture(self.source)
            if not capture.isOpened():
                time.sleep(self.reconnect_delay)
                continue
            try:
                while not self.stop_event.is_set():
                    ok, frame = capture.read()
                    if not ok:
                        break
                    self.frame_number += 1
                    if self.frame_number % self.frame_stride != 0:
                        continue
                    if self.target_resolution:
                        frame = cv2.resize(frame, self.target_resolution)
                    packet = FramePacket(
                        feed_id=self.feed_id,
                        source_id=str(self.source),
                        frame_number=self.frame_number,
                        captured_at=datetime.now(timezone.utc).isoformat(),
                        frame=frame,
                        source_width=int(frame.shape[1]),
                        source_height=int(frame.shape[0]),
                    )
                    try:
                        self.frames.put(packet, timeout=0.1)
                    except Full:
                        try:
                            self.frames.get_nowait()
                            self.frames.put_nowait(packet)
                        except (Empty, Full):
                            pass
            finally:
                capture.release()
            if isinstance(self.source, str) and Path(self.source).is_file():
                self.ended = True
                return
            if not self.stop_event.is_set():
                time.sleep(self.reconnect_delay)
