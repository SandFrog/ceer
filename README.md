# CEE Responsiveness Ranking

An intranet web application that lets multiple users add CEE contacts and rank
them by email responsiveness. Users vote a contact as **Helpful** (responds
immediately) or **No response** (ignores emails). No accounts or login are
required.

## How it works

- Anyone submits a contact's **name**, **title**, **email**, and **group**
  (one of ten industry groups, from a dropdown). Duplicate emails are rejected.
- Each browser gets a cookie used as an anonymous voter key. Each voter gets
  one vote per contact, and can change it at any time (re-voting overwrites).
  The cookie expires after **14 days**: once it does, the next vote gets a new
  key, so the same person can submit a fresh rating per contact every two
  weeks — useful because a CEE's responsiveness changes over time. All
  previous votes remain counted; the recency line reflects the most recent
  ones.
- Contacts are ranked by a **decayed Bayesian score**. Every vote has a weight
  based on age: a vote counts 1.0 when cast, half after 90 days, and about 2%
  after a year (`DECAY_HALF_LIFE_DAYS` in `database.py`). The score is
  `(weighted_helpful + 2.5) / (weighted_total + 5)`, where the sums use the
  decayed weights. A contact with no votes starts neutral at 0.5, fresh votes
  move the score much more than old ones, and ratings track *current*
  responsiveness: if a responsive client goes silent, their old helpful votes
  fade out and their ranking drops without anyone re-voting. Re-voting
  refreshes that vote's timestamp and therefore its weight.
- Each card shows a **recency line**: when the contact was last voted helpful
  and last voted no response (e.g. "last helpful: 1 week ago"). Since contacts
  retire or move on over time, a stale timestamp signals that the ranking is
  out of date.
- The list can be filtered by group via the **Group** dropdown.
- Data is stored in a single SQLite file, `data.db`, created automatically on
  first start. Databases created before groups existed are migrated
  automatically (a group column is added; existing rows are left blank until
  edited).

## Project layout

```
├── server.py       # Flask app + API routes
├── database.py     # SQLite schema, queries, scoring
├── static/         # Frontend (HTML/CSS/JS), served by the app
├── pyproject.toml  # Project metadata + dependency requirements
└── uv.lock         # Pinned dependency versions (committed, do not edit)
```

## Dependencies

Everything is managed by [uv](https://docs.astral.sh/uv/). You do **not** need
Python, pip, or virtualenv on the host — uv downloads and manages its own
Python build, which is what makes this deployable on old servers with an
ancient (or entirely absent) system Python.

Runtime dependencies (resolved and pinned in `uv.lock`):

| Package      | Version | Purpose                                    |
|--------------|---------|--------------------------------------------|
| flask        | 3.x     | Web framework, routing, JSON API           |
| waitress    | 3.x     | Production WSGI server (replaces dev server) |
| jinja2, markupsafe, werkzeug, itsdangerous, click, blinker | (pinned) | Flask transitive dependencies |

The project requires Python >= 3.9, satisfied automatically by uv's managed
Python.

## Deployment with uv

### 1. Install uv

uv is a single static binary; no root access is needed.

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

This installs to `~/.local/bin`. If that directory is not on `PATH`, add it:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

If the server has no internet access of its own, download the uv binary on
another machine and copy it over — it is fully self-contained.

### 2. Install Python and dependencies

From the project directory:

```sh
uv sync
```

This creates a `.venv` in the project directory, downloads a compatible
managed Python if the system one is too old or missing, and installs every
dependency at exactly the version pinned in `uv.lock`. Rerunning `uv sync`
after an update is the full upgrade procedure.

### 3. Run

Development / quick start:

```sh
uv run python server.py
```

Production (recommended for shared use — Flask's built-in server is not meant
for this):

```sh
uv run waitress-serve --host=0.0.0.0 --port=5000 server:app
```

The site is then available at `http://<server-host>:5000/`.

### 4. Run as a service (optional, Linux)

Create `/etc/systemd/system/cee-test.service`:

```ini
[Unit]
Description=CEE Responsiveness Ranking
After=network.target

[Service]
WorkingDirectory=/opt/cee-test
ExecStart=/root/.local/bin/uv run waitress-serve --host=0.0.0.0 --port=5000 server:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Adjust the uv path (from `which uv`) and `WorkingDirectory` to your install
location, then:

```sh
sudo systemctl enable --now cee-test
```

## Configuration

| Setting | Default | How to change |
|---------|---------|---------------|
| Port    | 5000    | `--port` flag on `waitress-serve` (or `PORT` env var with `python server.py`) |
| Bind address | 0.0.0.0 | `--host` flag (or `HOST` env var with `python server.py`) |
| Database | `./data.db` | Move the project directory; the file is created next to `server.py` |

Back up `data.db` to back up all contacts and votes.

## API

| Method | Path | Body / params | Description |
|--------|------|---------------|-------------|
| GET    | `/api/groups` | — | The list of industry groups |
| GET    | `/api/people` | `sort=score\|helpful\|newest\|name`, `group=<group>` (optional) | Ranked list with vote counts, `last_helpful` / `last_no_response` timestamps, and your current vote |
| POST   | `/api/people` | `{name, title, email, group}` | Add a contact (400 on unknown group, 409 on duplicate email) |
| POST   | `/api/people/:id/vote` | `{type: "helpful" \| "no_response"}` | Cast or change your vote |

## Industry groups

Agriculture and Prepared Products; Apparel, Footwear and Textiles; Automotive
and Aerospace; Base Metals; Consumer Products and Mass Merchandising;
Electronics; Industrial and Manufacturing Materials; Machinery; Petroleum,
Natural Gas and Minerals; Pharmaceuticals, Health and Chemicals.

The canonical list lives in `GROUPS` in `database.py` and is served at
`/api/groups`; the frontend builds its dropdowns from that endpoint.

## Notes and limitations

- Vote deduplication is cookie-based and lasts 14 days. Clearing cookies or
  using another browser allows additional votes sooner. This is acceptable for
  an internal tool but is not tamper-proof.
- There is no authentication by design; anyone who can reach the server can
  add contacts and vote. Only deploy on a trusted intranet.
