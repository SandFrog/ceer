import os, secrets
from flask import Flask, jsonify, request, send_from_directory
import database as db

app = Flask(__name__, static_folder="static", static_url_path="")

VOTER_COOKIE = "voter_key"
# A voter key is valid for 14 days; after that a new key is issued, so the
# same browser can submit a fresh rating per contact every two weeks.
VOTER_COOKIE_MAX_AGE = 14 * 24 * 60 * 60 # why does it do this??

db.init_db()


def voter_key():
    """Stable per-browser key stored in a long-lived cookie."""
    key = request.cookies.get(VOTER_COOKIE)
    return key if key else None


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/people")
def api_list_people():
    group = request.args.get("group") or None
    if group is not None and group not in db.GROUPS:
        return jsonify(error="unknown group"), 400
    rows = db.list_people(request.args.get("sort", "score"), group)
    key = voter_key()
    if key:
        with db.get_db() as conn:
            for row in rows:
                r = conn.execute(
                    "SELECT type FROM vote WHERE person_id = ? AND voter_key = ?",
                    (row["id"], key),
                ).fetchone()
                row["your_vote"] = r["type"] if r else None
    else:
        for row in rows:
            row["your_vote"] = None
    return jsonify(rows)


@app.get("/api/groups")
def api_groups():
    return jsonify(db.GROUPS)


@app.post("/api/people")
def api_add_person():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    title = (data.get("title") or "").strip()
    email = (data.get("email") or "").strip()
    group = (data.get("group") or "").strip()

    if not name or not title or not email:
        return jsonify(error="name, title and email are all required"), 400
    if group not in db.GROUPS:
        return jsonify(error="group is required and must be one of the defined groups"), 400
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return jsonify(error="invalid email address"), 400

    existing = db.person_exists(email)
    if existing:
        return jsonify(error="a person with that email already exists", id=existing), 409

    person_id = db.add_person(name, title, email, group)
    return jsonify(id=person_id), 201


@app.post("/api/people/<int:person_id>/vote")
def api_vote(person_id):
    if db.get_person(person_id) is None:
        return jsonify(error="person not found"), 404

    data = request.get_json(silent=True) or {}
    vote_type = data.get("type")
    if vote_type not in ("helpful", "no_response"):
        return jsonify(error="type must be 'helpful' or 'no_response'"), 400

    key = voter_key() or secrets.token_hex(16)
    db.cast_vote(person_id, vote_type, key)

    resp = jsonify(ok=True)
    resp.set_cookie(VOTER_COOKIE, key, max_age=VOTER_COOKIE_MAX_AGE)
    return resp


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
    )
