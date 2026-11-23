import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "data.db"

# Bayesian ranking prior: a person starts at 0.5 and needs real votes to move.
# (weighted_helpful + PRIOR_WEIGHT * PRIOR_MEAN) / (weighted_total + PRIOR_WEIGHT)
PRIOR_WEIGHT = 5
PRIOR_MEAN = 0.5

# Time decay: a vote's weight halves every DECAY_HALF_LIFE_DAYS days.
# A vote cast today counts 1.0, one 90 days ago 0.5, one year ago ~0.02.
# Rankings therefore track current responsiveness, not lifetime history.
DECAY_HALF_LIFE_DAYS = 90

GROUPS = [
    "Agriculture and Prepared Products",
    "Apparel, Footwear and Textiles",
    "Automotive and Aerospace",
    "Base Metals",
    "Consumer Products and Mass Merchandising",
    "Electronics",
    "Industrial and Manufacturing Materials",
    "Machinery",
    "Petroleum, Natural Gas and Minerals",
    "Pharmaceuticals, Health and Chemicals",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS person (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    title      TEXT NOT NULL,
    email      TEXT NOT NULL,
    grp        TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vote (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id  INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    type       TEXT NOT NULL CHECK (type IN ('helpful', 'no_response')),
    voter_key  TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (person_id, voter_key)
);

CREATE INDEX IF NOT EXISTS idx_vote_person ON vote(person_id);
"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
        # Migration for databases created before the group column existed.
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(person)")]
        if "grp" not in cols:
            conn.execute("ALTER TABLE person ADD COLUMN grp TEXT NOT NULL DEFAULT ''")


def vote_weight(created_at):
    """Exponential decay: 1.0 today, halved every DECAY_HALF_LIFE_DAYS days."""
    then = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=timezone.utc
    )
    age_days = (datetime.now(timezone.utc) - then).total_seconds() / 86400
    return 0.5 ** (age_days / DECAY_HALF_LIFE_DAYS)


def list_people(sort="score", group=None):
    """Return people (optionally one group) with decay-weighted scores and
    unweighted vote counts for display."""
    where = "WHERE p.grp = ?" if group else ""
    params = [group] if group else []

    with get_db() as conn:
        people = [
            dict(r)
            for r in conn.execute(
                f"""
                SELECT p.id, p.name, p.title, p.email, p.grp, p.created_at
                FROM person p
                {where}
                """,
                params,
            )
        ]
        votes = conn.execute(
            f"""
            SELECT v.person_id, v.type, v.created_at
            FROM vote v
            JOIN person p ON p.id = v.person_id
            {where}
            """,
            params,
        ).fetchall()

    agg = {
        p["id"]: {
            "helpful": 0,
            "no_response": 0,
            "total": 0,
            "weighted_helpful": 0.0,
            "weighted_total": 0.0,
            "last_helpful": None,
            "last_no_response": None,
        }
        for p in people
    }

    for v in votes:
        a = agg[v["person_id"]]
        a["total"] += 1
        a["weighted_total"] += vote_weight(v["created_at"])
        if v["type"] == "helpful":
            a["helpful"] += 1
            a["weighted_helpful"] += vote_weight(v["created_at"])
            if a["last_helpful"] is None or v["created_at"] > a["last_helpful"]:
                a["last_helpful"] = v["created_at"]
        else:
            a["no_response"] += 1
            if a["last_no_response"] is None or v["created_at"] > a["last_no_response"]:
                a["last_no_response"] = v["created_at"]

    for p in people:
        a = agg[p["id"]]
        p.update(a)
        p["score"] = (p["weighted_helpful"] + PRIOR_WEIGHT * PRIOR_MEAN) / (
            p["weighted_total"] + PRIOR_WEIGHT
        )

    sort_keys = {
        "score": lambda p: (-p["score"], -p["total"], p["name"].lower()),
        "helpful": lambda p: (-p["helpful"], -p["total"], p["name"].lower()),
        "newest": lambda p: (p["created_at"], -p["id"]),
        "name": lambda p: p["name"].lower(),
    }.get(sort, lambda p: (-p["score"], -p["total"], p["name"].lower()))
    people.sort(key=sort_keys)
    return people


def get_person(person_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, name, title, email, grp FROM person WHERE id = ?", (person_id,)
        ).fetchone()
        return dict(row) if row else None


def person_exists(email):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM person WHERE lower(email) = lower(?)", (email.strip(),)
        ).fetchone()
        return row["id"] if row else None


def add_person(name, title, email, group):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO person (name, title, email, grp) VALUES (?, ?, ?, ?)",
            (name.strip(), title.strip(), email.strip(), group.strip()),
        )
        return cur.lastrowid


def cast_vote(person_id, vote_type, voter_key):
    """One vote per voter per person; re-voting overwrites the previous choice."""
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO vote (person_id, type, voter_key)
            VALUES (?, ?, ?)
            ON CONFLICT (person_id, voter_key)
            DO UPDATE SET type = excluded.type, created_at = datetime('now')
            """,
            (person_id, vote_type, voter_key),
        )


def get_vote(person_id, voter_key):
    with get_db() as conn:
        row = conn.execute(
            "SELECT type FROM vote WHERE person_id = ? AND voter_key = ?",
            (person_id, voter_key),
        ).fetchone()
        return row["type"] if row else None
