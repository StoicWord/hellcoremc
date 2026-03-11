"""
╔══════════════════════════════════════════════════════════════╗
║          HELLCORE NETWORK — Flask Backend v7                ║
║  pip install flask mysql-connector-python                   ║
║  python app.py  →  http://localhost:5000                    ║
╠══════════════════════════════════════════════════════════════╣
║  DATABASE SETUP:                                            ║
║  Option A — Local MySQL:                                    ║
║    1. Run setup_mysql.sql in MySQL                          ║
║    2. Set USE_MYSQL_LOCAL = True below                      ║
║    3. Set LOCAL_MYSQL_* vars below                          ║
║                                                             ║
║  Option B — Aiven MySQL (cloud):                            ║
║    1. Set USE_MYSQL_LOCAL = False                           ║
║    2. Set AIVEN_* vars below                                ║
║                                                             ║
║  Option C — SQLite (zero setup, auto fallback):             ║
║    Just run python app.py — works instantly                 ║
╠══════════════════════════════════════════════════════════════╣
║  MAKE YOURSELF FOUNDER AFTER REGISTERING:                   ║
║  SQLite: sqlite3 hellcore.db                                ║
║    UPDATE hc_users SET role='founder'                       ║
║    WHERE username='YourName';                               ║
║                                                             ║
║  MySQL: UPDATE hc_users SET role='founder'                  ║
║    WHERE username='YourName';                               ║
╚══════════════════════════════════════════════════════════════╝
"""

import os, io, json, hashlib, secrets, sqlite3, traceback
import urllib.request, urllib.error, urllib.parse
from functools import wraps
from flask import Flask, request, jsonify, render_template, send_from_directory, Response

app = Flask(__name__)

# ═══════════════════════════════════════════════════════
# DATABASE CONFIGURATION — edit these to match your setup
# ═══════════════════════════════════════════════════════

# ── LOCAL MYSQL (running on your PC / localhost) ──────
USE_MYSQL_LOCAL = False          # Set True to use local MySQL
LOCAL_MYSQL_HOST     = "localhost"
LOCAL_MYSQL_PORT     = 3306
LOCAL_MYSQL_USER     = "root"
LOCAL_MYSQL_PASSWORD = "yourpassword"   # <── change this
LOCAL_MYSQL_DATABASE = "hellcore"

# ── AIVEN MYSQL (cloud) ───────────────────────────────
USE_MYSQL_AIVEN = False          # Set True to use Aiven
AIVEN_HOST     = "mysql-6c66671-aarushsen00-4e8a.j.aivencloud.com"
AIVEN_PORT     = 28286
AIVEN_USER     = "avnadmin"
AIVEN_PASSWORD = "AVNS_UnbfmnFGJ9tRcaj3ih9"
AIVEN_DATABASE = "defaultdb"

# ── SQLITE (zero-config fallback) ─────────────────────
SQLITE_FILE = "hellcore.db"

# Internal: which DB mode is actually active
_DB_MODE = "sqlite"  # will be set by try_connect()

# ═══════════════════════════════════════════════════════
# DB CONNECTION
# ═══════════════════════════════════════════════════════
def try_connect():
    global _DB_MODE
    if USE_MYSQL_LOCAL:
        try:
            import mysql.connector
            c = mysql.connector.connect(
                host=LOCAL_MYSQL_HOST, port=LOCAL_MYSQL_PORT,
                user=LOCAL_MYSQL_USER, password=LOCAL_MYSQL_PASSWORD,
                database=LOCAL_MYSQL_DATABASE, connection_timeout=6
            )
            c.close()
            _DB_MODE = "mysql_local"
            print(f"✓ Local MySQL connected ({LOCAL_MYSQL_HOST}:{LOCAL_MYSQL_PORT}/{LOCAL_MYSQL_DATABASE})")
            return
        except Exception as e:
            print(f"⚠ Local MySQL failed: {e}")

    if USE_MYSQL_AIVEN:
        try:
            import mysql.connector
            c = mysql.connector.connect(
                host=AIVEN_HOST, port=AIVEN_PORT,
                user=AIVEN_USER, password=AIVEN_PASSWORD,
                database=AIVEN_DATABASE, ssl_disabled=False,
                connection_timeout=8
            )
            c.close()
            _DB_MODE = "mysql_aiven"
            print(f"✓ Aiven MySQL connected ({AIVEN_HOST})")
            return
        except Exception as e:
            print(f"⚠ Aiven MySQL failed: {e}")

    _DB_MODE = "sqlite"
    print("✓ Using SQLite (hellcore.db) — zero config mode")

def get_db():
    if _DB_MODE in ("mysql_local", "mysql_aiven"):
        import mysql.connector
        if _DB_MODE == "mysql_local":
            return mysql.connector.connect(
                host=LOCAL_MYSQL_HOST, port=LOCAL_MYSQL_PORT,
                user=LOCAL_MYSQL_USER, password=LOCAL_MYSQL_PASSWORD,
                database=LOCAL_MYSQL_DATABASE
            )
        else:
            return mysql.connector.connect(
                host=AIVEN_HOST, port=AIVEN_PORT,
                user=AIVEN_USER, password=AIVEN_PASSWORD,
                database=AIVEN_DATABASE, ssl_disabled=False
            )
    else:
        conn = sqlite3.connect(SQLITE_FILE)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

def db_cursor(conn):
    if _DB_MODE in ("mysql_local", "mysql_aiven"):
        return conn.cursor(dictionary=True)
    return conn.cursor()

def to_dict(row):
    if row is None: return None
    if isinstance(row, dict): return row
    return dict(row)

def to_list(rows):
    return [to_dict(r) for r in rows]

def ph():
    """Placeholder: %s for MySQL, ? for SQLite"""
    return "%s" if _DB_MODE != "sqlite" else "?"

def phs(n):
    """n placeholders"""
    return ",".join([ph()] * n)

def upsert(c, table, cols_vals, conflict_cols):
    """INSERT OR REPLACE (SQLite) / INSERT ... ON DUPLICATE KEY UPDATE (MySQL)"""
    cols   = list(cols_vals.keys())
    vals   = list(cols_vals.values())
    if _DB_MODE == "sqlite":
        c.execute(
            f"INSERT OR REPLACE INTO {table}({','.join(cols)}) VALUES({phs(len(cols))})",
            vals
        )
    else:
        upd = ",".join(f"{col}=VALUES({col})" for col in cols if col not in conflict_cols)
        c.execute(
            f"INSERT INTO {table}({','.join(cols)}) VALUES({phs(len(cols))}) ON DUPLICATE KEY UPDATE {upd}",
            vals
        )

def ts(v): return str(v) if v else ""
def hp(pw): return hashlib.sha256(pw.encode()).hexdigest()

# ═══════════════════════════════════════════════════════
# INIT TABLES
# ═══════════════════════════════════════════════════════
def init_db():
    db = get_db(); c = db_cursor(db)
    mysql = _DB_MODE != "sqlite"
    AI  = "AUTO_INCREMENT" if mysql else "AUTOINCREMENT"
    DT  = "DATETIME DEFAULT CURRENT_TIMESTAMP" if mysql else "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    UNQ = "UNIQUE KEY uq" if mysql else "UNIQUE"

    tables = [
f"""CREATE TABLE IF NOT EXISTS hc_users(
  id INTEGER PRIMARY KEY {AI},
  email VARCHAR(200) UNIQUE NOT NULL,
  username VARCHAR(50) UNIQUE NOT NULL,
  mc_username VARCHAR(50) DEFAULT '',
  password_hash VARCHAR(100) NOT NULL,
  session_token VARCHAR(120),
  role VARCHAR(30) DEFAULT 'player',
  created_at {DT})""",

f"""CREATE TABLE IF NOT EXISTS hc_ranks(
  id INTEGER PRIMARY KEY {AI},
  user_id INTEGER NOT NULL,
  gamemode VARCHAR(30) NOT NULL,
  rank_name VARCHAR(30) DEFAULT 'default',
  {UNQ}(user_id,gamemode))""",

f"""CREATE TABLE IF NOT EXISTS hc_economy(
  user_id INTEGER PRIMARY KEY,
  server_gold INTEGER DEFAULT 0,
  server_iron INTEGER DEFAULT 0)""",

f"""CREATE TABLE IF NOT EXISTS hc_stats(
  id INTEGER PRIMARY KEY {AI},
  user_id INTEGER NOT NULL,
  gamemode VARCHAR(30) NOT NULL,
  kills INTEGER DEFAULT 0,
  deaths INTEGER DEFAULT 0,
  wins INTEGER DEFAULT 0,
  losses INTEGER DEFAULT 0,
  coins INTEGER DEFAULT 0,
  {UNQ}(user_id,gamemode))""",

f"""CREATE TABLE IF NOT EXISTS hc_inventory(
  id INTEGER PRIMARY KEY {AI},
  user_id INTEGER NOT NULL,
  item_type VARCHAR(30) DEFAULT 'rank',
  item_name VARCHAR(80) NOT NULL,
  gamemode VARCHAR(30) DEFAULT '',
  gifted_by INTEGER,
  status VARCHAR(20) DEFAULT 'active',
  created_at {DT})""",

f"""CREATE TABLE IF NOT EXISTS hc_gifts(
  id INTEGER PRIMARY KEY {AI},
  from_user_id INTEGER NOT NULL,
  to_username VARCHAR(50) NOT NULL,
  item_type VARCHAR(30) DEFAULT 'rank',
  item_name VARCHAR(80) NOT NULL,
  gamemode VARCHAR(30) DEFAULT '',
  status VARCHAR(20) DEFAULT 'pending',
  created_at {DT})""",

f"""CREATE TABLE IF NOT EXISTS hc_cart(
  id INTEGER PRIMARY KEY {AI},
  user_id INTEGER NOT NULL,
  item_id VARCHAR(60) NOT NULL,
  item_name VARCHAR(80) NOT NULL,
  item_price REAL NOT NULL,
  gamemode VARCHAR(30) DEFAULT '')""",

f"""CREATE TABLE IF NOT EXISTS hc_forums(
  id INTEGER PRIMARY KEY {AI},
  title VARCHAR(200) NOT NULL,
  content TEXT NOT NULL,
  author_id INTEGER NOT NULL,
  category VARCHAR(40) DEFAULT 'general',
  views INTEGER DEFAULT 0,
  created_at {DT})""",

f"""CREATE TABLE IF NOT EXISTS hc_replies(
  id INTEGER PRIMARY KEY {AI},
  forum_id INTEGER NOT NULL,
  author_id INTEGER NOT NULL,
  content TEXT NOT NULL,
  created_at {DT})""",

f"""CREATE TABLE IF NOT EXISTS hc_tickets(
  id INTEGER PRIMARY KEY {AI},
  title VARCHAR(200) NOT NULL,
  category VARCHAR(40) DEFAULT 'general',
  description TEXT NOT NULL,
  author_id INTEGER NOT NULL,
  status VARCHAR(20) DEFAULT 'open',
  created_at {DT})""",

f"""CREATE TABLE IF NOT EXISTS hc_ticket_msgs(
  id INTEGER PRIMARY KEY {AI},
  ticket_id INTEGER NOT NULL,
  author_id INTEGER NOT NULL,
  content TEXT NOT NULL,
  created_at {DT})""",
    ]

    for sql in tables:
        try: c.execute(sql)
        except Exception as e: print(f"  Table warn: {e}")

    db.commit(); c.close(); db.close()
    print(f"✓ Tables ready ({_DB_MODE})")

# ═══════════════════════════════════════════════════════
# AUTH HELPERS
# ═══════════════════════════════════════════════════════
STAFF_ROLES = ("helper","mod","dev","admin","owner","founder","youtube","famous")
ADMIN_ROLES = ("admin","owner","founder")

def get_user_by_token(token):
    if not token: return None
    try:
        db = get_db(); c = db_cursor(db)
        c.execute(f"SELECT * FROM hc_users WHERE session_token={ph()}", (token,))
        row = c.fetchone(); c.close(); db.close()
        return to_dict(row)
    except: return None

def auth_required(f):
    @wraps(f)
    def w(*a, **k):
        u = get_user_by_token(request.headers.get("X-Auth-Token",""))
        if not u: return jsonify({"error":"Not authenticated"}), 401
        request.cu = u; return f(*a, **k)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        u = get_user_by_token(request.headers.get("X-Auth-Token",""))
        if not u: return jsonify({"error":"Not authenticated"}), 401
        if u["role"] not in ADMIN_ROLES: return jsonify({"error":"Admin required"}), 403
        request.cu = u; return f(*a, **k)
    return w

# ═══════════════════════════════════════════════════════
# CORS
# ═══════════════════════════════════════════════════════
@app.after_request
def cors(r):
    r.headers["Access-Control-Allow-Origin"]  = "*"
    r.headers["Access-Control-Allow-Headers"] = "Content-Type,X-Auth-Token"
    r.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    return r

@app.route("/api/<path:p>", methods=["OPTIONS"])
def opts(p): return jsonify({}), 200

# ═══════════════════════════════════════════════════════
# FRONTEND
# ═══════════════════════════════════════════════════════
@app.route("/")
def index(): return render_template("index.html")

@app.route("/static/<path:f>")
def static_f(f): return send_from_directory("static", f)

# ═══════════════════════════════════════════════════════
# PROXY HELPERS — ALL external API calls go here
# Browser never touches Mojang/mc-heads directly → no CORS
# ═══════════════════════════════════════════════════════
def fetch_url(url, binary=False, timeout=8):
    req = urllib.request.Request(url, headers={
        "User-Agent": "HellcoreWebsite/7.0 (+mc.hellcore.in)"
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read() if binary else json.loads(r.read())

# ── Mojang UUID (for 3D skin viewer)
@app.route("/api/mc/uuid/<username>")
def mc_uuid(username):
    try:
        return jsonify(fetch_url(f"https://api.mojang.com/users/profiles/minecraft/{username}"))
    except urllib.error.HTTPError as e:
        return jsonify({"error":"Player not found" if e.code==404 else "Mojang error"}), e.code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Skin texture (for skinview3d) — tries mc-heads.net first, then Mojang session
@app.route("/api/skin/texture/<identifier>")
def skin_texture(identifier):
    """Returns raw PNG skin texture. identifier = UUID or username."""
    # Try mc-heads.net skin
    for url in [
        f"https://mc-heads.net/skin/{identifier}",
        f"https://minotar.net/skin/{identifier}",
    ]:
        try:
            data = fetch_url(url, binary=True)
            return Response(data, mimetype="image/png",
                headers={"Cache-Control": "public, max-age=300"})
        except: pass
    # Fallback: Steve skin (built into mc-heads)
    try:
        data = fetch_url("https://mc-heads.net/skin/Steve", binary=True)
        return Response(data, mimetype="image/png")
    except:
        return Response(b"", status=404)

# ── Cape texture — tries mc-heads, fallback 404
@app.route("/api/skin/cape/<identifier>")
def skin_cape(identifier):
    for url in [
        f"https://mc-heads.net/cape/{identifier}",
    ]:
        try:
            data = fetch_url(url, binary=True)
            return Response(data, mimetype="image/png",
                headers={"Cache-Control": "public, max-age=300"})
        except: pass
    return Response(b"", status=404)

# ── Head avatar image proxy (replaces crafatar heads)
@app.route("/api/skin/head/<identifier>")
@app.route("/api/skin/head/<identifier>/<int:size>")
def skin_head(identifier, size=64):
    for url in [
        f"https://mc-heads.net/avatar/{identifier}/{size}",
        f"https://minotar.net/avatar/{identifier}/{size}",
    ]:
        try:
            data = fetch_url(url, binary=True)
            return Response(data, mimetype="image/png",
                headers={"Cache-Control": "public, max-age=300"})
        except: pass
    return Response(b"", status=404)

# ── Server status
@app.route("/api/serverstatus")
def srv_status():
    try:
        return jsonify(fetch_url("https://api.mcsrvstat.us/3/mc.hellcore.in"))
    except Exception as e:
        return jsonify({"online": False, "error": str(e)})

# ═══════════════════════════════════════════════════════
# AUTH ROUTES
# ═══════════════════════════════════════════════════════
@app.route("/api/auth/register", methods=["POST"])
def register():
    try:
        d   = request.get_json(force=True) or {}
        em  = str(d.get("email","")).strip().lower()
        us  = str(d.get("username","")).strip()
        mc  = str(d.get("mc_username","")).strip()
        pw  = str(d.get("password",""))
        pw2 = str(d.get("confirm_password",""))

        if not em or not us or not pw:
            return jsonify({"error":"Email, username and password required"}), 400
        if "@" not in em or "." not in em:
            return jsonify({"error":"Enter a valid email address"}), 400
        if len(us) < 3 or len(us) > 20:
            return jsonify({"error":"Username must be 3–20 characters"}), 400
        if len(pw) < 6:
            return jsonify({"error":"Password must be at least 6 characters"}), 400
        if pw != pw2:
            return jsonify({"error":"Passwords do not match"}), 400

        db = get_db(); c = db_cursor(db)
        c.execute(f"SELECT id FROM hc_users WHERE email={ph()} OR username={ph()}", (em, us))
        if c.fetchone():
            db.close(); return jsonify({"error":"Email or username already taken"}), 409

        tok = secrets.token_hex(32)
        c.execute(
            f"INSERT INTO hc_users(email,username,mc_username,password_hash,session_token) VALUES({phs(5)})",
            (em, us, mc, hp(pw), tok)
        )
        uid = c.lastrowid

        # Create economy row
        if _DB_MODE == "sqlite":
            c.execute("INSERT OR IGNORE INTO hc_economy(user_id) VALUES(?)", (uid,))
        else:
            c.execute("INSERT INTO hc_economy(user_id) VALUES(%s) ON DUPLICATE KEY UPDATE user_id=user_id", (uid,))

        db.commit(); c.close(); db.close()
        return jsonify({"token":tok,"id":uid,"username":us,"email":em,"mc_username":mc,"role":"player"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error":f"Server error: {e}"}), 500

@app.route("/api/auth/login", methods=["POST"])
def login():
    try:
        d   = request.get_json(force=True) or {}
        idf = str(d.get("identifier","")).strip()
        pw  = str(d.get("password",""))

        db = get_db(); c = db_cursor(db)
        c.execute(
            f"SELECT * FROM hc_users WHERE (email={ph()} OR username={ph()}) AND password_hash={ph()}",
            (idf, idf, hp(pw))
        )
        row = to_dict(c.fetchone())
        if not row:
            db.close(); return jsonify({"error":"Wrong email/username or password"}), 401

        tok = secrets.token_hex(32)
        c.execute(f"UPDATE hc_users SET session_token={ph()} WHERE id={ph()}", (tok, row["id"]))
        db.commit(); c.close(); db.close()
        return jsonify({"token":tok,"id":row["id"],"username":row["username"],
                        "email":row["email"],"mc_username":row["mc_username"] or "","role":row["role"]})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error":f"Server error: {e}"}), 500

@app.route("/api/auth/logout", methods=["POST"])
@auth_required
def logout():
    db = get_db(); c = db_cursor(db)
    c.execute(f"UPDATE hc_users SET session_token=NULL WHERE id={ph()}", (request.cu["id"],))
    db.commit(); c.close(); db.close()
    return jsonify({"ok":True})

@app.route("/api/auth/me")
@auth_required
def auth_me():
    u = request.cu
    return jsonify({"id":u["id"],"username":u["username"],"email":u["email"],
                    "mc_username":u["mc_username"] or "","role":u["role"]})

# ═══════════════════════════════════════════════════════
# FORUMS
# ═══════════════════════════════════════════════════════
@app.route("/api/forums")
def forums_list():
    cat = request.args.get("cat","")
    db = get_db(); c = db_cursor(db)
    base = ("SELECT f.*, u.username author_name, u.role author_role, "
            f"(SELECT COUNT(*) FROM hc_replies r WHERE r.forum_id=f.id) reply_count "
            "FROM hc_forums f JOIN hc_users u ON f.author_id=u.id")
    if cat:
        c.execute(base + f" WHERE f.category={ph()} ORDER BY f.created_at DESC", (cat,))
    else:
        c.execute(base + " ORDER BY f.created_at DESC")
    rows = to_list(c.fetchall()); c.close(); db.close()
    for r in rows: r["created_at"] = ts(r["created_at"])
    return jsonify(rows)

@app.route("/api/forums/<int:fid>")
def forum_get(fid):
    db = get_db(); c = db_cursor(db)
    c.execute(f"UPDATE hc_forums SET views=views+1 WHERE id={ph()}", (fid,))
    c.execute(f"SELECT f.*, u.username author_name, u.role author_role "
              f"FROM hc_forums f JOIN hc_users u ON f.author_id=u.id WHERE f.id={ph()}", (fid,))
    forum = to_dict(c.fetchone())
    if not forum: db.close(); return jsonify({"error":"Not found"}), 404
    forum["created_at"] = ts(forum["created_at"])
    c.execute(f"SELECT r.*, u.username author_name, u.role author_role "
              f"FROM hc_replies r JOIN hc_users u ON r.author_id=u.id "
              f"WHERE r.forum_id={ph()} ORDER BY r.created_at ASC", (fid,))
    replies = to_list(c.fetchall())
    for r in replies: r["created_at"] = ts(r["created_at"])
    db.commit(); c.close(); db.close()
    return jsonify({"forum":forum,"replies":replies})

@app.route("/api/forums", methods=["POST"])
@auth_required
def forum_create():
    d = request.get_json(force=True) or {}
    if not d.get("title") or not d.get("content"):
        return jsonify({"error":"Title and content required"}), 400
    db = get_db(); c = db_cursor(db)
    c.execute(f"INSERT INTO hc_forums(title,content,author_id,category) VALUES({phs(4)})",
              (d["title"], d["content"], request.cu["id"], d.get("category","general")))
    db.commit(); fid = c.lastrowid; c.close(); db.close()
    return jsonify({"id":fid,"ok":True})

@app.route("/api/forums/<int:fid>", methods=["DELETE"])
@auth_required
def forum_del(fid):
    db = get_db(); c = db_cursor(db)
    c.execute(f"SELECT * FROM hc_forums WHERE id={ph()}", (fid,))
    f = to_dict(c.fetchone())
    if not f: db.close(); return jsonify({"error":"Not found"}), 404
    u = request.cu
    if f["author_id"] != u["id"] and u["role"] not in ADMIN_ROLES:
        db.close(); return jsonify({"error":"Forbidden"}), 403
    c.execute(f"DELETE FROM hc_replies WHERE forum_id={ph()}", (fid,))
    c.execute(f"DELETE FROM hc_forums  WHERE id={ph()}", (fid,))
    db.commit(); c.close(); db.close()
    return jsonify({"ok":True})

@app.route("/api/forums/<int:fid>/replies", methods=["POST"])
@auth_required
def reply_add(fid):
    d = request.get_json(force=True) or {}
    if not d.get("content"): return jsonify({"error":"Content required"}), 400
    db = get_db(); c = db_cursor(db)
    c.execute(f"INSERT INTO hc_replies(forum_id,author_id,content) VALUES({phs(3)})",
              (fid, request.cu["id"], d["content"]))
    db.commit(); c.close(); db.close()
    return jsonify({"ok":True})

@app.route("/api/forums/replies/<int:rid>", methods=["DELETE"])
@auth_required
def reply_del(rid):
    db = get_db(); c = db_cursor(db)
    c.execute(f"SELECT * FROM hc_replies WHERE id={ph()}", (rid,))
    r = to_dict(c.fetchone())
    if not r: db.close(); return jsonify({"error":"Not found"}), 404
    u = request.cu
    if r["author_id"] != u["id"] and u["role"] not in ADMIN_ROLES:
        db.close(); return jsonify({"error":"Forbidden"}), 403
    c.execute(f"DELETE FROM hc_replies WHERE id={ph()}", (rid,))
    db.commit(); c.close(); db.close()
    return jsonify({"ok":True})

# ═══════════════════════════════════════════════════════
# TICKETS
# ═══════════════════════════════════════════════════════
@app.route("/api/tickets")
@auth_required
def tickets_list():
    u = request.cu; db = get_db(); c = db_cursor(db)
    if u["role"] in STAFF_ROLES:
        c.execute("SELECT t.*, u.username author_name FROM hc_tickets t "
                  "JOIN hc_users u ON t.author_id=u.id ORDER BY t.created_at DESC")
    else:
        c.execute(f"SELECT t.*, u.username author_name FROM hc_tickets t "
                  f"JOIN hc_users u ON t.author_id=u.id WHERE t.author_id={ph()} ORDER BY t.created_at DESC",
                  (u["id"],))
    rows = to_list(c.fetchall()); c.close(); db.close()
    for r in rows: r["created_at"] = ts(r["created_at"])
    return jsonify(rows)

@app.route("/api/tickets", methods=["POST"])
@auth_required
def ticket_create():
    d = request.get_json(force=True) or {}
    if not d.get("title") or not d.get("description"):
        return jsonify({"error":"All fields required"}), 400
    db = get_db(); c = db_cursor(db)
    c.execute(f"INSERT INTO hc_tickets(title,description,author_id,category) VALUES({phs(4)})",
              (d["title"], d["description"], request.cu["id"], d.get("category","general")))
    db.commit(); tid = c.lastrowid; c.close(); db.close()
    return jsonify({"id":tid,"ok":True})

@app.route("/api/tickets/<int:tid>")
@auth_required
def ticket_get(tid):
    u = request.cu; db = get_db(); c = db_cursor(db)
    c.execute(f"SELECT t.*, u.username author_name FROM hc_tickets t "
              f"JOIN hc_users u ON t.author_id=u.id WHERE t.id={ph()}", (tid,))
    t = to_dict(c.fetchone())
    if not t: db.close(); return jsonify({"error":"Not found"}), 404
    if t["author_id"] != u["id"] and u["role"] not in STAFF_ROLES:
        db.close(); return jsonify({"error":"Forbidden"}), 403
    t["created_at"] = ts(t["created_at"])
    c.execute(f"SELECT m.*, u.username author_name, u.role author_role FROM hc_ticket_msgs m "
              f"JOIN hc_users u ON m.author_id=u.id WHERE m.ticket_id={ph()} ORDER BY m.created_at ASC", (tid,))
    msgs = to_list(c.fetchall())
    for m in msgs: m["created_at"] = ts(m["created_at"])
    c.close(); db.close()
    return jsonify({"ticket":t,"messages":msgs})

@app.route("/api/tickets/<int:tid>/msg", methods=["POST"])
@auth_required
def ticket_msg(tid):
    d = request.get_json(force=True) or {}
    if not d.get("content"): return jsonify({"error":"Content required"}), 400
    u = request.cu; db = get_db(); c = db_cursor(db)
    c.execute(f"SELECT * FROM hc_tickets WHERE id={ph()}", (tid,)); t = to_dict(c.fetchone())
    if not t: db.close(); return jsonify({"error":"Not found"}), 404
    if t["author_id"] != u["id"] and u["role"] not in STAFF_ROLES:
        db.close(); return jsonify({"error":"Forbidden"}), 403
    c.execute(f"INSERT INTO hc_ticket_msgs(ticket_id,author_id,content) VALUES({phs(3)})",
              (tid, u["id"], d["content"]))
    db.commit(); c.close(); db.close()
    return jsonify({"ok":True})

@app.route("/api/tickets/<int:tid>/close", methods=["POST"])
@auth_required
def ticket_close(tid):
    db = get_db(); c = db_cursor(db)
    c.execute(f"UPDATE hc_tickets SET status='closed' WHERE id={ph()}", (tid,))
    db.commit(); c.close(); db.close()
    return jsonify({"ok":True})

@app.route("/api/tickets/<int:tid>", methods=["DELETE"])
@auth_required
def ticket_del(tid):
    u = request.cu; db = get_db(); c = db_cursor(db)
    c.execute(f"SELECT * FROM hc_tickets WHERE id={ph()}", (tid,)); t = to_dict(c.fetchone())
    if not t: db.close(); return jsonify({"error":"Not found"}), 404
    if t["author_id"] != u["id"] and u["role"] not in ADMIN_ROLES:
        db.close(); return jsonify({"error":"Forbidden"}), 403
    c.execute(f"DELETE FROM hc_ticket_msgs WHERE ticket_id={ph()}", (tid,))
    c.execute(f"DELETE FROM hc_tickets WHERE id={ph()}", (tid,))
    db.commit(); c.close(); db.close()
    return jsonify({"ok":True})

# ═══════════════════════════════════════════════════════
# CART
# ═══════════════════════════════════════════════════════
@app.route("/api/cart")
@auth_required
def cart_get():
    db = get_db(); c = db_cursor(db)
    c.execute(f"SELECT * FROM hc_cart WHERE user_id={ph()}", (request.cu["id"],))
    rows = to_list(c.fetchall()); c.close(); db.close()
    return jsonify(rows)

@app.route("/api/cart", methods=["POST"])
@auth_required
def cart_add():
    d = request.get_json(force=True) or {}
    db = get_db(); c = db_cursor(db)
    c.execute(f"INSERT INTO hc_cart(user_id,item_id,item_name,item_price,gamemode) VALUES({phs(5)})",
              (request.cu["id"], d["item_id"], d["item_name"], float(d["item_price"]), d.get("gamemode","")))
    db.commit(); c.close(); db.close()
    return jsonify({"ok":True})

@app.route("/api/cart/<int:cid>", methods=["DELETE"])
@auth_required
def cart_rem(cid):
    db = get_db(); c = db_cursor(db)
    c.execute(f"DELETE FROM hc_cart WHERE id={ph()} AND user_id={ph()}", (cid, request.cu["id"]))
    db.commit(); c.close(); db.close()
    return jsonify({"ok":True})

@app.route("/api/cart/clear", methods=["DELETE"])
@auth_required
def cart_clear():
    db = get_db(); c = db_cursor(db)
    c.execute(f"DELETE FROM hc_cart WHERE user_id={ph()}", (request.cu["id"],))
    db.commit(); c.close(); db.close()
    return jsonify({"ok":True})

# ═══════════════════════════════════════════════════════
# INVENTORY & GIFTS
# ═══════════════════════════════════════════════════════
@app.route("/api/inventory")
@auth_required
def inventory():
    db = get_db(); c = db_cursor(db)
    c.execute(f"SELECT * FROM hc_inventory WHERE user_id={ph()} ORDER BY created_at DESC", (request.cu["id"],))
    rows = to_list(c.fetchall()); c.close(); db.close()
    for r in rows: r["created_at"] = ts(r["created_at"])
    return jsonify(rows)

@app.route("/api/gifts/send", methods=["POST"])
@auth_required
def gift_send():
    d = request.get_json(force=True) or {}
    to_nm = str(d.get("to_username","")).strip()
    db = get_db(); c = db_cursor(db)
    c.execute(f"SELECT id FROM hc_users WHERE username={ph()}", (to_nm,))
    if not c.fetchone(): db.close(); return jsonify({"error":"Player not found"}), 404
    c.execute(f"INSERT INTO hc_gifts(from_user_id,to_username,item_type,item_name,gamemode) VALUES({phs(5)})",
              (request.cu["id"], to_nm, d.get("item_type","rank"), d["item_name"], d.get("gamemode","")))
    db.commit(); c.close(); db.close()
    return jsonify({"ok":True})

@app.route("/api/gifts/pending")
@auth_required
def gifts_pending():
    db = get_db(); c = db_cursor(db)
    c.execute(f"SELECT g.*, u.username from_name FROM hc_gifts g "
              f"JOIN hc_users u ON g.from_user_id=u.id "
              f"WHERE g.to_username={ph()} AND g.status='pending'", (request.cu["username"],))
    rows = to_list(c.fetchall()); c.close(); db.close()
    for r in rows: r["created_at"] = ts(r.get("created_at",""))
    return jsonify(rows)

@app.route("/api/gifts/<int:gid>/claim", methods=["POST"])
@auth_required
def gift_claim(gid):
    u = request.cu; db = get_db(); c = db_cursor(db)
    c.execute(f"SELECT * FROM hc_gifts WHERE id={ph()} AND to_username={ph()} AND status='pending'",
              (gid, u["username"]))
    g = to_dict(c.fetchone())
    if not g: db.close(); return jsonify({"error":"Gift not found"}), 404
    c.execute(f"INSERT INTO hc_inventory(user_id,item_type,item_name,gamemode,gifted_by) VALUES({phs(5)})",
              (u["id"], g["item_type"], g["item_name"], g["gamemode"], g["from_user_id"]))
    c.execute(f"UPDATE hc_gifts SET status='claimed' WHERE id={ph()}", (gid,))
    db.commit(); c.close(); db.close()
    return jsonify({"ok":True})

# ═══════════════════════════════════════════════════════
# STATS & LEADERBOARD
# ═══════════════════════════════════════════════════════
@app.route("/api/stats/<username>")
def stats_get(username):
    db = get_db(); c = db_cursor(db)
    c.execute(f"SELECT * FROM hc_users WHERE username={ph()}", (username,))
    u = to_dict(c.fetchone())
    if not u: db.close(); return jsonify({"error":"Player not found"}), 404
    c.execute(f"SELECT * FROM hc_stats    WHERE user_id={ph()}", (u["id"],)); stats = to_list(c.fetchall())
    c.execute(f"SELECT * FROM hc_ranks    WHERE user_id={ph()}", (u["id"],)); ranks = to_list(c.fetchall())
    c.execute(f"SELECT * FROM hc_economy  WHERE user_id={ph()}", (u["id"],)); eco = to_dict(c.fetchone())
    c.close(); db.close()
    return jsonify({
        "user":    {"username":u["username"],"role":u["role"],"mc_username":u["mc_username"] or ""},
        "stats":   {s["gamemode"]:s for s in stats},
        "ranks":   {r["gamemode"]:r["rank_name"] for r in ranks},
        "economy": eco or {"server_gold":0,"server_iron":0}
    })

@app.route("/api/lb/<gamemode>")
def lb_get(gamemode):
    stat = request.args.get("stat","wins")
    if stat not in ("kills","deaths","wins","losses","coins"): stat = "wins"
    db = get_db(); c = db_cursor(db)
    c.execute(
        f"SELECT u.username, u.mc_username, r.rank_name, "
        f"s.kills, s.deaths, s.wins, s.losses, s.coins "
        f"FROM hc_stats s JOIN hc_users u ON s.user_id=u.id "
        f"LEFT JOIN hc_ranks r ON r.user_id=u.id AND r.gamemode={ph()} "
        f"WHERE s.gamemode={ph()} ORDER BY s.{stat} DESC LIMIT 50",
        (gamemode, gamemode)
    )
    rows = to_list(c.fetchall()); c.close(); db.close()
    return jsonify(rows)

@app.route("/api/staff")
def staff_list():
    db = get_db(); c = db_cursor(db)
    c.execute("SELECT username, mc_username, role FROM hc_users "
              "WHERE role IN ('helper','mod','dev','admin','owner','founder','youtube','famous')")
    rows = to_list(c.fetchall()); c.close(); db.close()
    return jsonify(rows)

# ═══════════════════════════════════════════════════════
# ADMIN
# ═══════════════════════════════════════════════════════
@app.route("/api/admin/users")
@admin_required
def admin_users():
    db = get_db(); c = db_cursor(db)
    c.execute("SELECT id,email,username,mc_username,role,created_at FROM hc_users ORDER BY created_at DESC")
    rows = to_list(c.fetchall()); c.close(); db.close()
    for r in rows: r["created_at"] = ts(r["created_at"])
    return jsonify(rows)

@app.route("/api/admin/users/<int:uid>/role", methods=["POST"])
@admin_required
def admin_role(uid):
    d = request.get_json(force=True) or {}
    role = d.get("role","player")
    if role not in ("player","helper","mod","dev","admin","owner","founder","youtube","famous"):
        return jsonify({"error":"Invalid role"}), 400
    db = get_db(); c = db_cursor(db)
    c.execute(f"UPDATE hc_users SET role={ph()} WHERE id={ph()}", (role, uid))
    db.commit(); c.close(); db.close()
    return jsonify({"ok":True})

@app.route("/api/admin/setstats", methods=["POST"])
@admin_required
def admin_setstats():
    d = request.get_json(force=True) or {}
    db = get_db(); c = db_cursor(db)
    c.execute(f"SELECT id FROM hc_users WHERE username={ph()}", (d["username"],))
    u = to_dict(c.fetchone())
    if not u: db.close(); return jsonify({"error":"User not found"}), 404
    upsert(c, "hc_stats",
        {"user_id":u["id"],"gamemode":d["gamemode"],"kills":d.get("kills",0),
         "deaths":d.get("deaths",0),"wins":d.get("wins",0),"losses":d.get("losses",0),"coins":d.get("coins",0)},
        {"user_id","gamemode"})
    db.commit(); c.close(); db.close()
    return jsonify({"ok":True})

@app.route("/api/admin/setrank", methods=["POST"])
@admin_required
def admin_setrank():
    d = request.get_json(force=True) or {}
    db = get_db(); c = db_cursor(db)
    c.execute(f"SELECT id FROM hc_users WHERE username={ph()}", (d["username"],))
    u = to_dict(c.fetchone())
    if not u: db.close(); return jsonify({"error":"User not found"}), 404
    upsert(c, "hc_ranks", {"user_id":u["id"],"gamemode":d["gamemode"],"rank_name":d["rank"]}, {"user_id","gamemode"})
    db.commit(); c.close(); db.close()
    return jsonify({"ok":True})

@app.route("/api/admin/seteco", methods=["POST"])
@admin_required
def admin_seteco():
    d = request.get_json(force=True) or {}
    db = get_db(); c = db_cursor(db)
    c.execute(f"SELECT id FROM hc_users WHERE username={ph()}", (d["username"],))
    u = to_dict(c.fetchone())
    if not u: db.close(); return jsonify({"error":"User not found"}), 404
    upsert(c, "hc_economy", {"user_id":u["id"],"server_gold":d.get("gold",0),"server_iron":d.get("iron",0)}, {"user_id"})
    db.commit(); c.close(); db.close()
    return jsonify({"ok":True})

@app.route("/api/tebex/webhook", methods=["POST"])
def tebex():
    d = request.get_json(force=True) or {}
    if d.get("type") == "payment.completed":
        uname = d.get("player",{}).get("username","")
        if uname:
            db = get_db(); c = db_cursor(db)
            c.execute(f"SELECT * FROM hc_users WHERE mc_username={ph()} OR username={ph()}", (uname,uname))
            u = to_dict(c.fetchone())
            if u:
                for pkg in d.get("packages",[]):
                    c.execute(f"INSERT INTO hc_inventory(user_id,item_type,item_name,gamemode) VALUES({phs(4)})",
                              (u["id"],"rank",pkg.get("name",""),pkg.get("category","global")))
            db.commit(); c.close(); db.close()
    return jsonify({"ok":True})

@app.route("/api/health")
def health():
    return jsonify({"status":"ok","db":_DB_MODE,"version":"7.0"})

# ═══════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 56)
    print("  HELLCORE NETWORK — Backend v7")
    print("=" * 56)
    try_connect()
    try:
        init_db()
    except Exception as e:
        print(f"⚠ DB init error: {e}"); traceback.print_exc()
    print("=" * 56)
    print("  Running on http://localhost:5000")
    print("=" * 56)
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
