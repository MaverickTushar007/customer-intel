from ingestion.frame_sampler import stream_frames
from ultralytics import YOLO
from tracking.position_tracker import PositionTracker
import cv2
import sqlite3
from datetime import datetime, timezone, timedelta

detector = YOLO('yolo11n.pt')

CONF_THRESHOLD = 0.25
VIDEO_START = datetime.now(timezone.utc)

def video_ts_to_iso(ts):
    return (VIDEO_START + timedelta(seconds=ts)).isoformat()

token_colors = {}

SERVICE_ZONE = [(360, 180), (482, 180), (482, 360), (360, 360)]

def in_service_zone(centroid):
    x, y = centroid
    return 360 <= x <= 482 and 180 <= y <= 360

DB = sqlite3.connect('db/customer_intel.db')
DB.execute("DELETE FROM wait_metrics")
DB.execute("DELETE FROM persons")
DB.commit()

def get_color(token_id):
    if token_id not in token_colors:
        import numpy as np
        np.random.seed(hash(token_id) % (2**32))
        token_colors[token_id] = tuple(int(x) for x in np.random.randint(80, 255, 3))
    return token_colors[token_id]

def log_person(token, entry_ts, camera_id):
    DB.execute(
        "INSERT OR IGNORE INTO persons (token_id, first_seen, camera_id) VALUES (?,?,?)",
        (token, video_ts_to_iso(entry_ts), camera_id))
    DB.commit()

def log_exit(token, entry_ts, exit_ts, served_tokens):
    wait = exit_ts - entry_ts
    if wait <= 2:
        return
    date = VIDEO_START.strftime('%Y-%m-%d')
    abandoned = 0 if token in served_tokens else 1
    DB.execute(
        "INSERT INTO wait_metrics (token_id, entry_time, exit_time, wait_seconds, abandoned, date) VALUES (?,?,?,?,?,?)",
        (token, video_ts_to_iso(entry_ts), video_ts_to_iso(exit_ts), round(wait, 2), abandoned, date))
    DB.execute(
        "UPDATE persons SET last_seen=?, abandoned=? WHERE token_id=?",
        (video_ts_to_iso(exit_ts), abandoned, token))
    DB.commit()
    print(f"  [DB] {token} exited — dwell: {wait:.1f}s")

VIDEOS = [
    ("vidssave.com Surya Security Cctv Hik 2MP _ 1080p  cafe TP Surabaya 20170623 1080P.mp4", "cam_surya"),
    ("vidssave.com HD CCTV Camera video 3MP 4MP iProx CCTV HDCCTVCameras.net retail store 720p.mp4", "cam_retail"),
    ("test_video.mp4", "cam_test"),
]

print("Pipeline running — press Q to quit")

for _vid, _cam in VIDEOS:
    print(f"\n--- Processing {_cam} ---")
    tracker = PositionTracker(max_distance=150, max_missing_frames=150)
    served_tokens = set()

    for fid, ts, frame in stream_frames(_vid, fps_target=8):
        results = detector(frame, conf=CONF_THRESHOLD, classes=[0], verbose=False)
        bboxes = [box.xyxy[0].tolist() for box in results[0].boxes]

        tracks = tracker.update(bboxes, fid, ts)

        for token, bbox, is_new in tracks:
            cx = (bbox[0]+bbox[2])/2
            cy = (bbox[1]+bbox[3])/2
            if in_service_zone((cx, cy)):
                served_tokens.add(token)
            if is_new:
                log_person(token, ts, _cam)
                print(f"[{ts:.1f}s] NEW person: {token}")
            color = get_color(token)
            x1, y1, x2, y2 = [int(v) for v in bbox]
            cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
            cv2.putText(frame, token, (x1, max(y1-6,10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        for token, entry_ts, exit_ts in tracker.get_exited(fid):
            log_exit(token, entry_ts, exit_ts, served_tokens)

        cv2.rectangle(frame, (360,180), (482,360), (0,165,255), 2)
        cv2.putText(frame, 'SERVICE', (362,175), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,165,255), 1)
        cv2.putText(frame, f"Tracked: {len(tracker.tracks)} | t={ts:.1f}s",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
        cv2.imshow('Position Tracker', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    for token, entry_ts, exit_ts in tracker.flush_all():
        log_exit(token, entry_ts, exit_ts, served_tokens)
        DB.execute(
            "UPDATE persons SET last_seen=? WHERE token_id=? AND last_seen IS NULL",
            (video_ts_to_iso(exit_ts), token))
    DB.commit()
    print(f"--- Done {_cam} ---")

cv2.destroyAllWindows()
DB.close()
print("\nAll done.")
