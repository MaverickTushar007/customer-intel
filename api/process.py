import os, uuid, threading, time
import cv2
import numpy as np
import torch
from ultralytics import YOLO
import torchreid
import sqlite3
from datetime import datetime, timezone, timedelta

jobs = {}  # job_id -> {status, progress, stage, result}

detector = None
embedder = None

def load_models():
    global detector, embedder
    if detector is None:
        detector = YOLO('yolo11n.pt')
    if embedder is None:
        embedder = torchreid.models.build_model(
            name='osnet_x1_0', num_classes=1000, pretrained=True)
        embedder.eval()

def get_embedding(frame, bbox, device):
    x1, y1, x2, y2 = [int(v) for v in bbox]
    if (y2 - y1) < 40:
        return None
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    crop = cv2.resize(crop, (128, 256))
    inp = crop.astype(np.float32) / 255.0
    inp = (inp - np.array([0.485,0.456,0.406])) / np.array([0.229,0.224,0.225])
    inp = np.transpose(inp, (2,0,1))
    tensor = torch.tensor(inp).unsqueeze(0).float().to(device)
    with torch.no_grad():
        feat = embedder(tensor)
    feat = feat.cpu().numpy().flatten()
    return feat / (np.linalg.norm(feat) + 1e-8)

def process_video(job_id, video_path):
    try:
        jobs[job_id] = {"status": "running", "progress": 0,
                        "stage": "Loading models...", "result": None}

        load_models()
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        embedder.to(device)

        jobs[job_id]["stage"] = "Detecting people..."
        jobs[job_id]["progress"] = 10

        VIDEO_START = datetime.now(timezone.utc)
        gallery = {}
        tracks = {}
        last_seen_frame = {}
        last_seen_ts = {}
        REID_THRESHOLD = 0.65

        def video_ts_to_iso(ts):
            return (VIDEO_START + timedelta(seconds=ts)).isoformat()

        cap = cv2.VideoCapture(video_path)
        native_fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        skip = max(1, int(native_fps / 8))
        frame_id = 0

        DB = sqlite3.connect('db/customer_intel.db')
        DB.execute("DELETE FROM wait_metrics")
        DB.execute("DELETE FROM persons")
        DB.commit()

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_id % skip == 0:
                ts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

                # Update progress
                progress = 10 + int((frame_id / max(total_frames, 1)) * 70)
                stage = "Detecting people..." if progress < 30 else \
                        "Building identity profiles..." if progress < 55 else \
                        "Analysing behaviour..."
                jobs[job_id]["progress"] = progress
                jobs[job_id]["stage"] = stage

                results = detector(frame, conf=0.25, classes=[0], verbose=False)
                for box in results[0].boxes:
                    emb = get_embedding(frame, box.xyxy[0].tolist(), device)
                    if emb is None:
                        continue

                    best_token, best_score = None, 0.0
                    for tid, stored in gallery.items():
                        score = float(np.dot(emb, stored))
                        if score > best_score:
                            best_score = score
                            best_token = tid

                    if best_score >= REID_THRESHOLD:
                        gallery[best_token] = 0.9*gallery[best_token] + 0.1*emb
                        gallery[best_token] /= np.linalg.norm(gallery[best_token])
                        token, is_new = best_token, False
                    else:
                        token = str(uuid.uuid4())[:8]
                        gallery[token] = emb
                        is_new = True

                    last_seen_frame[token] = frame_id
                    last_seen_ts[token] = ts

                    if is_new:
                        entry_iso = video_ts_to_iso(ts)
                        tracks[token] = {'entry_ts': ts, 'entry_iso': entry_iso}
                        cur = DB.cursor()
                        cur.execute(
                            "INSERT OR IGNORE INTO persons (token_id, first_seen, camera_id) VALUES (?,?,?)",
                            (token, entry_iso, 'cam_01'))
                        DB.commit()

                for token, last_fid in list(last_seen_frame.items()):
                    if token in tracks and (frame_id - last_fid) > 30:
                        exit_ts = last_seen_ts[token]
                        wait = exit_ts - tracks[token]['entry_ts']
                        if wait > 0:
                            date = VIDEO_START.strftime('%Y-%m-%d')
                            cur = DB.cursor()
                            cur.execute(
                                "INSERT INTO wait_metrics (token_id, entry_time, exit_time, wait_seconds, abandoned, date) VALUES (?,?,?,?,?,?)",
                                (token, tracks[token]['entry_iso'],
                                 video_ts_to_iso(exit_ts), round(wait,2), 1, date))
                            cur.execute(
                                "UPDATE persons SET last_seen=?, abandoned=1 WHERE token_id=?",
                                (video_ts_to_iso(exit_ts), token))
                            DB.commit()
                        del tracks[token]
                        del last_seen_frame[token]
                        del last_seen_ts[token]

            frame_id += 1

        # Log remaining
        for token, track in tracks.items():
            exit_ts = last_seen_ts.get(token, track['entry_ts'])
            wait = exit_ts - track['entry_ts']
            if wait > 0:
                date = VIDEO_START.strftime('%Y-%m-%d')
                cur = DB.cursor()
                cur.execute(
                    "INSERT INTO wait_metrics (token_id, entry_time, exit_time, wait_seconds, abandoned, date) VALUES (?,?,?,?,?,?)",
                    (token, track['entry_iso'], video_ts_to_iso(exit_ts),
                     round(wait,2), 1, date))
                DB.commit()

        cap.release()
        DB.close()
        os.remove(video_path)

        jobs[job_id]["stage"] = "Generating insights..."
        jobs[job_id]["progress"] = 95
        time.sleep(1)
        jobs[job_id]["status"] = "done"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["stage"] = "Complete"

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["stage"] = f"Error: {str(e)}"

def start_job(video_path):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "queued", "progress": 0, "stage": "Queued", "result": None}
    t = threading.Thread(target=process_video, args=(job_id, video_path))
    t.daemon = True
    t.start()
    return job_id
