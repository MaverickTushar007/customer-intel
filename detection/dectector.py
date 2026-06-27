# detection/detector.py

from ultralytics import YOLO
import numpy as np

class PersonDetector:
    def __init__(self, model_path="yolo11n.pt", conf=0.6):
        self.model = YOLO(model_path)
        self.conf = conf

    def detect(self, frame):
        """
        Returns list of dicts: {bbox: [x1,y1,x2,y2], conf: float}
        Filters to person class only (COCO class 0).
        """
        results = self.model(frame, conf=self.conf, classes=[0], verbose=False)
        detections = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "conf": float(box.conf[0])
                })
        return detections