# WMark Studio — Telegram Watermark Bot + Mini App

A professional, production-shaped Telegram bot that watermarks photos and
videos, with a full **Mini App (Telegram WebApp)** editor so people can build
and tweak watermark templates like they would on a website — live preview,
sliders, position grid, text or logo watermarks, video "screen movement",
video tails, and per-channel auto-watermarking.

Built from scratch (original code) to match the *feature set* shown in your
reference screenshots — not copied from any existing bot.

---

## Architecture

```
wmarkbot/
├── bot/                      # Telegram bot (Pyrofork / Pyrogram fork)
│   ├── config.py             # All settings, loaded from .env
│   ├── main.py                # Bot entrypoint
│   ├── database/
│   │   ├── models.py          # SQLAlchemy models: User, Template, Tail, Channel, Job
│   │   ├── db.py              # Async engine/session
│   │   └── crud.py            # All DB queries (shared by bot + webapp)
│   ├── handlers/               # Pyrogram plugin handlers (auto-loaded)
│   │   ├── start.py            # /start, main menu, Mini App launch button
│   │   ├── templates.py        # /templates, quick "send a PNG" template creation
│   │   ├── tails.py            # /tails management
│   │   ├── channels_admin.py   # channel admin detection + auto-watermark posts
│   │   ├── media.py             # direct photo/video watermarking in DM
│   │   └── profile.py           # /profile, plan display, upgrade stub
│   └── utils/
│       ├── image_watermark.py   # Pillow-based photo watermark engine
│       ├── video_watermark.py   # ffmpeg-based video watermark engine
│       ├── processor.py          # dispatches template -> correct engine
│       └── telegram_auth.py      # validates Mini App initData (HMAC) + JWT
│
├── webapp_server/             # FastAPI backend that serves + powers the Mini App
│   ├── main.py                  # app entrypoint, mounts API + static files
│   ├── routes_auth.py            # POST /api/auth (Telegram initData -> JWT)
│   ├── routes_templates.py       # CRUD for templates
│   ├── routes_process.py         # POST /api/process (upload + apply watermark)
│   ├── routes_misc.py             # profile, tails, channels
│   ├── deps.py                     # JWT auth dependency
│   └── schemas.py                  # Pydantic request/response models
│
├── webapp/                    # Mini App frontend (vanilla HTML/CSS/JS)
│   ├── index.html
│   ├── css/style.css
│   └── js/{api.js, preview.js, app.js}
│
├── storage/                    # runtime data (uploads, watermark images, tails, output, db)
├── requirements.txt
├── .env.example
└── run.py                      # dev convenience launcher (bot + webapp together)
```

**Why this split?** The bot handles chat-native, low-friction flows (send a
photo, get it watermarked; send a PNG, get a template). The Mini App handles
everything that's painful over chat: sliders, live preview, multi-field forms.
Both talk to the *same* SQLite database and the *same* watermarking engine
(`bot/utils/processor.py`), so a template created in the bot immediately shows
up in the Mini App and vice versa.

---

## 1. Prerequisites

- Python 3.11+
- **ffmpeg** installed on the host (required for video watermarking):
  ```bash
  sudo apt-get update && sudo apt-get install -y ffmpeg
  ```
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- API ID/hash from <https://my.telegram.org> (required by Pyrofork even for bots)
- A public HTTPS domain to host the Mini App (Telegram **requires** HTTPS —
  `http://localhost` will NOT work inside the Telegram client). For local
  development, use `ngrok http 8080` or `cloudflared tunnel --url http://localhost:8080`.

## 2. Setup

```bash
cd wmarkbot
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# now edit .env: fill in API_ID, API_HASH, BOT_TOKEN, BOT_USERNAME, WEBAPP_URL
```

### Configure your bot with @BotFather

1. `/newbot` → get your token → put it in `.env` as `BOT_TOKEN`
2. `/mybots` → your bot → **Bot Settings** → **Menu Button** → **Configure Menu Button**
   → set the URL to your `WEBAPP_URL` (this makes the Mini App reachable via
   the chat's menu button, in addition to the in-message buttons this project
   already sends).
3. `/mybots` → your bot → **Bot Settings** → **Configure Mini App / Web App**
   if prompted, or just rely on the `web_app` buttons already wired into
   `/start`, `/templates`, `/tails`, `/channels` in this project — no extra
   BotFather step is strictly required for those to work.

## 3. Run it

**Local development (bot + webapp in one process):**
```bash
python run.py
```
Then in another terminal, expose port 8080 publicly (Telegram needs HTTPS):
```bash
ngrok http 8080
```
Copy the `https://...ngrok-free.app` URL into `.env` as `WEBAPP_URL`, restart, done.

**Production (recommended: two separate services):**
```bash
# Service 1 — the bot
python -m bot.main

# Service 2 — the webapp (behind nginx/caddy with real TLS)
uvicorn webapp_server.main:app --host 0.0.0.0 --port 8080 --workers 2
```

Example `systemd` units and an nginx reverse-proxy config are in `deploy/` —
see the note at the bottom of this file if you'd like those generated too.

## 4. Try it

1. Open your bot in Telegram, send `/start`.
2. Tap **🎨 Open Watermark Studio** — the Mini App opens.
3. In the **Editor** tab, tap the upload box, pick a photo.
4. Go to **Templates** → **+** → choose *Photo* or *Text*, upload a logo or
   type your text, drag the sliders, tap a position — the preview updates live.
5. Save, go back to **Editor**, select the template, tap **Apply watermark** —
   the processed file downloads.
6. For channels: add your bot as **admin** to any channel you own. It's
   auto-detected and you'll get a DM to assign a template to it from the
   **Channels** tab. From then on, every photo/video posted to that channel
   is automatically re-posted with the watermark applied.

---

## Feature checklist (matches your reference screenshots)

| Reference feature | Where it lives |
|---|---|
| Horizontal/Vertical offset %, Width %, Opacity %, Rotation ° sliders | Mini App → Template editor |
| 9-point position grid + Random + Fill | Mini App → Template editor, `bot/utils/image_watermark.py` / `video_watermark.py` |
| "Screen movement" (animated watermark on video) | Template editor toggle → `video_watermark.py::_movement_expr` (DVD-bounce motion) |
| Text or Photo watermark type | Template editor segmented control |
| "From file" quick template creation | `/templates` → send PNG directly in chat |
| "In editor" full builder | Mini App |
| Plans (Lite/Normal/Pro) with template/channel/traffic limits | `bot/config.py::PLAN_LIMITS`, enforced in `crud.py` and API routes |
| Video tails | `bot/handlers/tails.py`, `video_watermark.py::_append_tail` |
| Channels list with per-channel template assignment | `bot/handlers/channels_admin.py`, Mini App → Channels tab |
| Profile: plan, traffic used/limit | `/profile`, Mini App → Profile tab |

---

## Security notes

- **Mini App auth is real, not a stub.** `bot/utils/telegram_auth.py`
  validates the HMAC signature of Telegram's `initData` exactly per the
  [official spec](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app).
  Never remove this check — without it, anyone could impersonate any user.
- Change `JWT_SECRET` in `.env` to a long random string before deploying.
- File uploads are size-capped (`MAX_UPLOAD_MB`) and type-checked.
- Per-user daily traffic quota is enforced server-side on every processing
  request (bot and webapp both call the same `crud.add_usage` accounting).

## Extending it

- **Payments**: `bot/handlers/profile.py::plan_select` and the Mini App's
  upgrade buttons are stubs — wire up Telegram Stars (`sendInvoice` with
  `currency="XTR"`) or a payment provider, then call a `crud.set_plan(...)`
  helper (add one next to `set_default_template` in `crud.py`).
- **Swap SQLite for Postgres**: just change `DATABASE_URL` in `.env` and
  `pip install asyncpg`; no code changes needed thanks to SQLAlchemy.
- **S3/object storage** instead of local disk: swap the `Path.write_bytes`
  calls in `webapp_server/routes_*.py` and `bot/handlers/*.py` for your
  storage client of choice; the DB only ever stores a path/URL string.
