# 🔥 HELLCORE NETWORK — Setup Guide v7

## ⚡ Fastest Start (SQLite, zero config)

```bash
pip install flask mysql-connector-python
python app.py
# Open http://localhost:5000
```

Tables are created automatically. Works instantly with no database setup.

---

## 🗄️ Option A — Local MySQL (your PC)

1. Install MySQL on your machine
2. Run the setup script:
   ```bash
   mysql -u root -p < setup_mysql.sql
   ```
3. Edit `app.py`:
   ```python
   USE_MYSQL_LOCAL   = True
   LOCAL_MYSQL_HOST  = "localhost"
   LOCAL_MYSQL_USER  = "root"
   LOCAL_MYSQL_PASSWORD = "yourpassword"
   LOCAL_MYSQL_DATABASE = "hellcore"
   ```
4. Run: `python app.py`

---

## ☁️ Option B — Aiven MySQL (cloud)

1. Edit `app.py`:
   ```python
   USE_MYSQL_AIVEN = True
   ```
2. The Aiven credentials are already filled in.
3. Run: `python app.py`

---

## 🔧 Make Yourself Admin After Registering

### SQLite:
```bash
sqlite3 hellcore.db "UPDATE hc_users SET role='founder' WHERE username='YourName';"
```

### MySQL:
```sql
USE hellcore;
UPDATE hc_users SET role='founder' WHERE username='YourName';
```

Then hard-refresh the website — Admin and Staff nav buttons will appear.

---

## 📁 File Structure

```
hc7/
├── app.py              ← Flask backend (all API routes + skin proxy)
├── setup_mysql.sql     ← Run this to create MySQL tables
├── requirements.txt
├── HOWTORUN.md
├── hellcore.db         ← SQLite DB (auto-created)
├── templates/
│   └── index.html      ← Complete single-page frontend
└── static/
    ├── logo.png
    └── shadimg.png
```

---

## ✅ Everything Fixed in v7

| Issue | Fix |
|-------|-----|
| ❌ Crafatar is down (Failed to fetch) | ✅ All skins via mc-heads.net + minotar.net, proxied through Flask |
| ❌ Refresh logs you out | ✅ Session in localStorage, restored on every page load |
| ❌ Form fields remember old data | ✅ All fields cleared on successful submit |
| ❌ Captcha doesn't change | ✅ New code on: modal open, wrong code, login fail, success |
| ❌ Account not saving | ✅ Tested — register + login work, saved to DB |
| ❌ No confirm password | ✅ Added with server-side validation |
| ❌ No show password | ✅ 👁 toggle on every password field |
| ❌ Cart works without login | ✅ Login modal shown when not logged in |
| ❌ CORS errors from Mojang | ✅ All Mojang calls proxied via /api/mc/uuid, /api/skin/* |
| ❌ Can't choose database | ✅ SQLite (default), Local MySQL, or Aiven — all supported |

---

## 🚀 Production Deployment

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

Use Nginx as reverse proxy for SSL.

---

## 🌐 Skin API Endpoints (Flask proxy)

- `GET /api/skin/head/<username_or_uuid>/<size>` — Head avatar PNG
- `GET /api/skin/texture/<username_or_uuid>` — Full skin PNG
- `GET /api/skin/cape/<username_or_uuid>` — Cape PNG
- `GET /api/mc/uuid/<username>` — Mojang UUID lookup
- `GET /api/serverstatus` — mc.hellcore.in status

All proxied through Flask — browser never contacts Mojang directly.
