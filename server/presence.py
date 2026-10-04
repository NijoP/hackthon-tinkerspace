"""Person-entry detection for the kitchen camera (local, GPU if available).

Perception only: this module reports "a person is present / just entered". The server
decides what to say (greeting), keeping PERCEPTION -> DECISION -> OUTPUT separate.

Detector: torchvision Faster R-CNN MobileNetV3-FPN (COCO "person" class). Unlike the
old HOG + face cascade, it handles partial bodies and high, downward camera angles.

Entry logic (debounced so one person walking in triggers exactly one greeting):
  * present  = a person seen in at least ENTRY_HITS of the last ENTRY_WINDOW checks
  * absent   = no person seen for ABSENT_RESET_S seconds
  * entry    = absent -> present transition, and no greeting in the last GREET_COOLDOWN_S
"""

from __future__ import annotations

import collections
import os
import threading
import time
from typing import Callable, Optional

import numpy as np

CHECK_INTERVAL_S = float(os.getenv("PRESENCE_INTERVAL_S", "0.5"))
SCORE_MIN = float(os.getenv("PRESENCE_SCORE_MIN", "0.6"))
MIN_BOX_FRACTION = float(os.getenv("PRESENCE_MIN_BOX_FRACTION", "0.02"))
ENTRY_WINDOW = 3
ENTRY_HITS = 2
ABSENT_RESET_S = float(os.getenv("PRESENCE_ABSENT_RESET_S", "30"))
GREET_COOLDOWN_S = float(os.getenv("PRESENCE_GREET_COOLDOWN_S", "90"))


class PersonDetector:
    def __init__(self) -> None:
        import torch
        from torchvision.models.detection import (
            FasterRCNN_MobileNet_V3_Large_FPN_Weights,
            fasterrcnn_mobilenet_v3_large_fpn,
        )

        self._torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        model = fasterrcnn_mobilenet_v3_large_fpn(
            weights=FasterRCNN_MobileNet_V3_Large_FPN_Weights.DEFAULT, box_score_thresh=0.4
        )
        self.model = model.eval().to(self.device)

    def detect(self, bgr: np.ndarray) -> list[dict]:
        torch = self._torch
        h, w = bgr.shape[:2]
        rgb = np.ascontiguousarray(bgr[:, :, ::-1])
        x = torch.from_numpy(rgb).permute(2, 0, 1).float().div(255).to(self.device)
        with torch.inference_mode():
            out = self.model([x])[0]
        people = []
        for box, label, score in zip(out["boxes"], out["labels"], out["scores"]):
            if int(label) != 1 or float(score) < SCORE_MIN:
                continue
            x1, y1, x2, y2 = [float(v) for v in box]
            if (x2 - x1) * (y2 - y1) < MIN_BOX_FRACTION * w * h:
                continue
            people.append({"score": round(float(score), 2),
                           "box": [round(x1 / w, 3), round(y1 / h, 3), round(x2 / w, 3), round(y2 / h, 3)]})
        return people


class PresenceMonitor:
    """Background loop: fetch latest frame -> detect -> debounce -> on_entry callback."""

    def __init__(self, get_frame: Callable[[], tuple[Optional[bytes], str]],
                 on_entry: Callable[[dict], None]) -> None:
        self._get_frame = get_frame
        self._on_entry = on_entry
        self.enabled = os.getenv("PRESENCE_ENABLED", "1") != "0"
        self.state = {
            "status": "starting",        # starting | running | error | off
            "present": False,
            "people": [],
            "source": None,
            "last_seen_at": None,
            "last_greet_at": None,
            "device": None,
            "error": None,
            "infer_ms": None,
        }
        self._hits: collections.deque[bool] = collections.deque(maxlen=ENTRY_WINDOW)
        self._lock = threading.Lock()
        threading.Thread(target=self._run, name="presence", daemon=True).start()

    def snapshot(self) -> dict:
        with self._lock:
            s = dict(self.state)
        s["enabled"] = self.enabled
        return s

    def mark_greeted(self) -> None:
        """A greeting happened another way (e.g. the user said 'I am in the kitchen')."""
        with self._lock:
            self.state["last_greet_at"] = time.time()
            self.state["present"] = True
            self.state["last_seen_at"] = time.time()

    def _run(self) -> None:
        import cv2

        try:
            detector = PersonDetector()
            with self._lock:
                self.state.update(status="running", device=detector.device)
        except Exception as exc:  # pragma: no cover - depends on host
            with self._lock:
                self.state.update(status="error", error=f"{type(exc).__name__}: {exc}")
            return

        while True:
            time.sleep(CHECK_INTERVAL_S)
            if not self.enabled:
                with self._lock:
                    self.state.update(status="off", people=[])
                continue
            jpeg, source = self._get_frame()
            if not jpeg:
                with self._lock:
                    self.state.update(status="running", people=[], source=None)
                self._update(False)
                continue
            frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue
            t0 = time.time()
            try:
                people = detector.detect(frame)
            except Exception as exc:
                with self._lock:
                    self.state.update(error=f"{type(exc).__name__}: {exc}")
                continue
            with self._lock:
                self.state.update(status="running", people=people, source=source,
                                  infer_ms=int((time.time() - t0) * 1000), error=None)
            self._update(bool(people))

    def _update(self, seen: bool) -> None:
        now = time.time()
        self._hits.append(seen)
        entry = None
        with self._lock:
            if seen:
                self.state["last_seen_at"] = now
            was_present = self.state["present"]
            if not was_present and sum(self._hits) >= ENTRY_HITS:
                self.state["present"] = True
                last_greet = self.state["last_greet_at"] or 0
                if now - last_greet >= GREET_COOLDOWN_S:
                    self.state["last_greet_at"] = now
                    entry = {"source": self.state["source"], "people": list(self.state["people"])}
            elif was_present:
                last_seen = self.state["last_seen_at"] or 0
                if now - last_seen >= ABSENT_RESET_S:
                    self.state["present"] = False  # left the kitchen; next entry greets again
        if entry is not None:
            try:
                self._on_entry(entry)
            except Exception:
                pass
