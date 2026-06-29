from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent.query_agent import ask
import sqlite3

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class NLQuery(BaseModel):
    question: str

@app.post("/ask")
def query(q: NLQuery):
    result = ask(q.question)
    return {"result": result}

@app.get("/cameras")
def cameras():
    db = sqlite3.connect("db/customer_intel.db")
    rows = db.execute("SELECT DISTINCT camera_id FROM persons ORDER BY camera_id").fetchall()
    db.close()
    return {"cameras": ["all"] + [r[0] for r in rows]}

@app.get("/stats")
def stats(camera: str = Query(default="all")):
    db = sqlite3.connect("db/customer_intel.db")
    cam_filter = "" if camera == "all" else f"AND p.camera_id = '{camera}'"
    cam_filter_w = "" if camera == "all" else f"AND w.token_id IN (SELECT token_id FROM persons WHERE camera_id = '{camera}')"

    persons_raw = db.execute(f"""
        SELECT p.token_id, p.first_seen, p.last_seen,
               p.camera_id, w.wait_seconds, w.abandoned
        FROM persons p
        LEFT JOIN wait_metrics w ON p.token_id = w.token_id
        WHERE 1=1 {cam_filter}
        ORDER BY w.wait_seconds DESC
    """).fetchall()

    persons = [
        {{"token_id": r[0], "first_seen": r[1], "last_seen": r[2],
          "camera_id": r[3], "wait_seconds": r[4], "abandoned": r[5]}}
        for r in persons_raw
    ]

    data = {{
        "total_visitors": db.execute(f"SELECT COUNT(*) FROM persons WHERE 1=1 {cam_filter}").fetchone()[0],
        "avg_dwell": db.execute(f"SELECT ROUND(AVG(wait_seconds),1) FROM wait_metrics w WHERE wait_seconds > 2 {cam_filter_w}").fetchone()[0],
        "max_dwell": db.execute(f"SELECT ROUND(MAX(wait_seconds),1) FROM wait_metrics w WHERE 1=1 {cam_filter_w}").fetchone()[0],
        "abandonment_rate": db.execute(f"SELECT ROUND(100.0 * SUM(abandoned) / COUNT(*), 1) FROM wait_metrics w WHERE wait_seconds > 2 {cam_filter_w}").fetchone()[0],
        "persons": persons
    }}
    db.close()
    return data
