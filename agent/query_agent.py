from groq import Groq
import sqlite3
import json
import os

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

SCHEMA = """
Tables:
- persons(token_id TEXT, first_seen TEXT, last_seen TEXT, camera_id TEXT, abandoned INTEGER)
- wait_metrics(id INTEGER, token_id TEXT, entry_time TEXT, exit_time TEXT, wait_seconds REAL, abandoned INTEGER, date TEXT)

Notes:
- abandoned=1 means person left before being attended
- wait_seconds is total dwell time in the venue
- dates stored as YYYY-MM-DD strings
- timestamps are ISO8601 UTC strings
"""

SYSTEM = f"""You are a business intelligence assistant for a restaurant/venue analytics platform.
You answer questions by writing SQLite SELECT queries against this schema:

{SCHEMA}

Rules:
- Return ONLY the raw SQL query, nothing else
- No markdown, no explanation, no backticks
- Always use SELECT, never INSERT/UPDATE/DELETE
"""

def ask(question: str) -> dict:
    db = sqlite3.connect('db/customer_intel.db')
    msg = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": question}
        ],
        max_tokens=256,
        temperature=0
    )
    sql = msg.choices[0].message.content.strip()
    print(f"\nSQL: {sql}\n")
    try:
        cur = db.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        result = [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        result = {"error": str(e), "sql": sql}
    finally:
        db.close()
    return result

if __name__ == "__main__":
    questions = [
        "How many total visitors have we had?",
        "What is the average dwell time in seconds?",
        "Which person stayed the longest and for how long?",
        "How many people abandoned without being served?",
    ]
    for q in questions:
        print(f"Q: {q}")
        result = ask(q)
        print(f"A: {json.dumps(result, indent=2)}")
        print("-" * 50)
