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
                 reconnect_delay: float = 2.0, target_resolution: tuple[int, int] | None = None,
                 loop: bool = False):
        self.feed_id = feed_id
        self.source = int(source) if isinstance(source, str) and source.isdigit() else source
        self.frames = frames
        self.frame_stride = max(1, frame_stride)
        self.reconnect_delay = reconnect_delay
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.frame_number = 0
        self.target_resolution = target_resolution
        self.loop = loop
        self.ended = False
        self.preview_path = None

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name=f"capture-{self.feed_id}", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3.0)

    @staticmethod
    def open_capture(source):
        if isinstance(source, str) and source.startswith(("rtsp://", "http://", "https://")):
            return cv2.VideoCapture(source, cv2.CAP_FFMPEG, [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000,
            ])
        return cv2.VideoCapture(source)

    def _run(self) -> None:
        while not self.stop_event.is_set():
            capture = self.open_capture(self.source)
            last_preview = 0
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
                    if self.preview_path and time.monotonic() - last_preview >= 1:
                        temp = self.preview_path.with_suffix(".tmp.jpg")
                        if cv2.imwrite(str(temp), frame):
                            temp.replace(self.preview_path)
                        last_preview = time.monotonic()
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
                if self.loop and not self.stop_event.is_set():
                    self.frame_number = 0
                    continue
                self.ended = True
                return
            if not self.stop_event.is_set():
                time.sleep(self.reconnect_delay)
