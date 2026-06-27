from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
from groq import Groq
import os

app = FastAPI(title="Customer Intelligence API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def get_db():
    return sqlite3.connect('db/customer_intel.db')

SCHEMA = """
Tables:
- persons(token_id TEXT, first_seen TEXT, last_seen TEXT, camera_id TEXT, abandoned INTEGER)
- wait_metrics(id INTEGER, token_id TEXT, entry_time TEXT, exit_time TEXT, wait_seconds REAL, abandoned INTEGER, date TEXT)
Notes:
- abandoned=1 means left without being served
- wait_seconds is dwell time in seconds
- The 'date' column only exists in wait_metrics, NOT in persons
- To filter by today use: WHERE date = date('now') on wait_metrics
- Only count visits where wait_seconds > 2 to exclude false detections
"""

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/metrics/summary")
def summary():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT COUNT(*), ROUND(AVG(wait_seconds),1), ROUND(MAX(wait_seconds),1),
               SUM(CASE WHEN abandoned=1 THEN 1 ELSE 0 END)
        FROM wait_metrics
        WHERE wait_seconds > 2
    """)
    r = cur.fetchone()
    db.close()
    total = r[0] or 0
    abandoned = r[3] or 0
    return {
        "total_visitors": total,
        "avg_dwell_seconds": r[1],
        "max_dwell_seconds": r[2],
        "abandoned_count": abandoned,
        "abandonment_rate_pct": round((abandoned / total) * 100, 1) if total else 0
    }

@app.get("/metrics/persons")
def all_persons():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT p.token_id, p.first_seen, p.camera_id, w.wait_seconds, w.abandoned
        FROM persons p
        LEFT JOIN wait_metrics w ON p.token_id = w.token_id
        WHERE w.wait_seconds > 2
        ORDER BY p.first_seen
    """)
    rows = cur.fetchall()
    db.close()
    return [{"token_id": r[0], "entered": r[1], "camera": r[2],
             "dwell_seconds": r[3], "abandoned": bool(r[4])} for r in rows]

@app.get("/metrics/longest_waits")
def longest_waits(limit: int = 5):
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT token_id, wait_seconds, entry_time, abandoned
        FROM wait_metrics
        WHERE wait_seconds > 2
        ORDER BY wait_seconds DESC LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    db.close()
    return [{"token_id": r[0], "dwell_seconds": r[1],
             "entered": r[2], "abandoned": bool(r[3])} for r in rows]

class Question(BaseModel):
    question: str

@app.post("/ask")
def ask(body: Question):
    db = get_db()
    sql_msg = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": f"You write SQLite SELECT queries for this schema:\n{SCHEMA}\nReturn ONLY raw SQL, no markdown, no explanation. Always filter with wait_seconds > 2."},
            {"role": "user", "content": body.question}
        ],
        max_tokens=200, temperature=0
    )
    sql = sql_msg.choices[0].message.content.strip()
    try:
        cur = db.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        result = [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        db.close()
        return {"question": body.question, "sql": sql,
                "plain_answer": f"Sorry, could not answer that. ({e})", "result": []}
    finally:
        db.close()

    plain_msg = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a friendly business analyst explaining venue analytics to a restaurant owner. Give a clear plain English answer in 1-2 sentences. Never mention token IDs, SQL, or technical terms."},
            {"role": "user", "content": f"Question: {body.question}\nData: {result}"}
        ],
        max_tokens=150, temperature=0.3
    )
    return {"question": body.question, "sql": sql, "result": result,
            "plain_answer": plain_msg.choices[0].message.content.strip()}
