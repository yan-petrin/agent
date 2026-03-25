import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict

DB_PATH = "hol_agency.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS bloggers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            telegram TEXT,
            email TEXT,
            platforms TEXT DEFAULT '{}',
            niche TEXT,
            language TEXT DEFAULT 'pt-BR',
            rate REAL,
            status TEXT DEFAULT 'prospect',
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            client TEXT,
            budget REAL,
            start_date TEXT,
            end_date TEXT,
            status TEXT DEFAULT 'planning',
            description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS campaign_bloggers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            blogger_id INTEGER NOT NULL,
            stage TEXT DEFAULT 'invited',
            agreed_rate REAL,
            payment_status TEXT DEFAULT 'pending',
            post_url TEXT,
            notes TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
            FOREIGN KEY (blogger_id) REFERENCES bloggers(id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            assignee TEXT,
            status TEXT DEFAULT 'open',
            priority TEXT DEFAULT 'normal',
            deadline TEXT,
            blogger_id INTEGER,
            campaign_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (blogger_id) REFERENCES bloggers(id),
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
        );
    """)
    conn.commit()
    conn.close()


def _now():
    return datetime.now().isoformat()


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


# ─── Bloggers ──────────────────────────────────────────────────────────────────

def add_blogger(name: str, telegram: str = None, email: str = None,
                platforms: dict = None, niche: str = None, language: str = "pt-BR",
                rate: float = None, status: str = "prospect", notes: str = None) -> Dict:
    conn = _conn()
    now = _now()
    cur = conn.execute(
        "INSERT INTO bloggers (name,telegram,email,platforms,niche,language,rate,status,notes,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (name, telegram, email, json.dumps(platforms or {}), niche, language, rate, status, notes, now, now),
    )
    row = dict(conn.execute("SELECT * FROM bloggers WHERE id=?", (cur.lastrowid,)).fetchone())
    conn.commit()
    conn.close()
    row["platforms"] = json.loads(row["platforms"])
    return row


def search_bloggers(query: str = None, status: str = None, platform: str = None) -> List[Dict]:
    conn = _conn()
    q = "SELECT * FROM bloggers WHERE 1=1"
    params = []
    if query:
        q += " AND (name LIKE ? OR telegram LIKE ? OR email LIKE ? OR niche LIKE ?)"
        params += [f"%{query}%"] * 4
    if status:
        q += " AND status = ?"
        params.append(status)
    if platform:
        q += " AND platforms LIKE ?"
        params.append(f"%{platform}%")
    q += " ORDER BY name"
    rows = [dict(r) for r in conn.execute(q, params).fetchall()]
    conn.close()
    for r in rows:
        r["platforms"] = json.loads(r["platforms"])
    return rows


def update_blogger(blogger_id: int, **kwargs) -> Optional[Dict]:
    conn = _conn()
    if "platforms" in kwargs and isinstance(kwargs["platforms"], dict):
        kwargs["platforms"] = json.dumps(kwargs["platforms"])
    kwargs["updated_at"] = _now()
    allowed = {"name", "telegram", "email", "platforms", "niche", "language",
               "rate", "status", "notes", "updated_at"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        conn.close()
        return None
    clause = ", ".join(f"{k}=?" for k in updates)
    conn.execute(f"UPDATE bloggers SET {clause} WHERE id=?", [*updates.values(), blogger_id])
    conn.commit()
    row = conn.execute("SELECT * FROM bloggers WHERE id=?", (blogger_id,)).fetchone()
    conn.close()
    if not row:
        return None
    result = dict(row)
    result["platforms"] = json.loads(result["platforms"])
    return result


# ─── Campaigns ─────────────────────────────────────────────────────────────────

def create_campaign(name: str, client: str = None, budget: float = None,
                    start_date: str = None, end_date: str = None,
                    status: str = "planning", description: str = None) -> Dict:
    conn = _conn()
    now = _now()
    cur = conn.execute(
        "INSERT INTO campaigns (name,client,budget,start_date,end_date,status,description,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (name, client, budget, start_date, end_date, status, description, now, now),
    )
    row = dict(conn.execute("SELECT * FROM campaigns WHERE id=?", (cur.lastrowid,)).fetchone())
    conn.commit()
    conn.close()
    return row


def link_blogger_to_campaign(campaign_id: int, blogger_id: int, stage: str = "invited",
                              agreed_rate: float = None, payment_status: str = "pending",
                              post_url: str = None, notes: str = None) -> Dict:
    conn = _conn()
    cur = conn.execute(
        "INSERT INTO campaign_bloggers (campaign_id,blogger_id,stage,agreed_rate,payment_status,post_url,notes,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (campaign_id, blogger_id, stage, agreed_rate, payment_status, post_url, notes, _now()),
    )
    row = dict(conn.execute("SELECT * FROM campaign_bloggers WHERE id=?", (cur.lastrowid,)).fetchone())
    conn.commit()
    conn.close()
    return row


def update_campaign_blogger(campaign_id: int, blogger_id: int, **kwargs) -> Optional[Dict]:
    conn = _conn()
    kwargs["updated_at"] = _now()
    allowed = {"stage", "agreed_rate", "payment_status", "post_url", "notes", "updated_at"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    clause = ", ".join(f"{k}=?" for k in updates)
    conn.execute(
        f"UPDATE campaign_bloggers SET {clause} WHERE campaign_id=? AND blogger_id=?",
        [*updates.values(), campaign_id, blogger_id],
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM campaign_bloggers WHERE campaign_id=? AND blogger_id=?",
        (campaign_id, blogger_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_campaign_report(campaign_id: int) -> Dict:
    conn = _conn()
    campaign = conn.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
    if not campaign:
        conn.close()
        return {"error": f"Кампания #{campaign_id} не найдена"}

    rows = conn.execute("""
        SELECT cb.*, b.name, b.telegram, b.email, b.platforms
        FROM campaign_bloggers cb
        JOIN bloggers b ON b.id = cb.blogger_id
        WHERE cb.campaign_id = ?
    """, (campaign_id,)).fetchall()
    conn.close()

    bloggers = []
    total_agreed = 0.0
    paid = 0.0
    for r in rows:
        d = dict(r)
        d["platforms"] = json.loads(d.get("platforms") or "{}")
        bloggers.append(d)
        total_agreed += d.get("agreed_rate") or 0
        if d.get("payment_status") == "paid":
            paid += d.get("agreed_rate") or 0

    by_stage = {}
    for b in bloggers:
        by_stage.setdefault(b["stage"], []).append(b["name"])

    return {
        "campaign": dict(campaign),
        "total_bloggers": len(bloggers),
        "by_stage": {k: len(v) for k, v in by_stage.items()},
        "budget": dict(campaign).get("budget"),
        "total_agreed": total_agreed,
        "paid": paid,
        "remaining": total_agreed - paid,
        "bloggers": bloggers,
    }


# ─── Tasks ─────────────────────────────────────────────────────────────────────

def create_task(title: str, description: str = None, assignee: str = None,
                deadline: str = None, priority: str = "normal",
                blogger_id: int = None, campaign_id: int = None) -> Dict:
    conn = _conn()
    now = _now()
    cur = conn.execute(
        "INSERT INTO tasks (title,description,assignee,deadline,priority,blogger_id,campaign_id,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (title, description, assignee, deadline, priority, blogger_id, campaign_id, now, now),
    )
    row = dict(conn.execute("SELECT * FROM tasks WHERE id=?", (cur.lastrowid,)).fetchone())
    conn.commit()
    conn.close()
    return row


def list_tasks(status: str = None, assignee: str = None,
               blogger_id: int = None, campaign_id: int = None) -> List[Dict]:
    conn = _conn()
    q = "SELECT * FROM tasks WHERE 1=1"
    params = []
    if status:
        q += " AND status=?"
        params.append(status)
    if assignee:
        q += " AND assignee LIKE ?"
        params.append(f"%{assignee}%")
    if blogger_id:
        q += " AND blogger_id=?"
        params.append(blogger_id)
    if campaign_id:
        q += " AND campaign_id=?"
        params.append(campaign_id)
    q += " ORDER BY created_at DESC"
    rows = [dict(r) for r in conn.execute(q, params).fetchall()]
    conn.close()
    return rows


def update_task(task_id: int, **kwargs) -> Optional[Dict]:
    conn = _conn()
    kwargs["updated_at"] = _now()
    allowed = {"title", "description", "assignee", "status", "priority",
               "deadline", "blogger_id", "campaign_id", "updated_at"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    clause = ", ".join(f"{k}=?" for k in updates)
    conn.execute(f"UPDATE tasks SET {clause} WHERE id=?", [*updates.values(), task_id])
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
