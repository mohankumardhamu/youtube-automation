# youtube-n8n — Tech sites → YouTube Shorts

An n8n workflow (running in Docker) that turns a list of tech web pages into YouTube Shorts:

```
URLs (form / manual list)
  └─ for each URL (one at a time)
       Fetch page ─ Extract text ─ Claude writes script, title, description, hashtags
       ─ VEED avatar video (fal.ai queue, polled every 30s, 20 min max)
       ─ Download MP4 ─ Upload to YouTube ─ log
  └─ Run Summary (uploaded / skipped, with reasons)
```

If a URL fails at any step (bot-blocked page, too little text, API error, VEED timeout), it is logged as **skipped** and the loop moves on to the next URL.

## Files

| Path | Purpose |
|---|---|
| `docker-compose.yml` | n8n (`stable` tag), bound to `127.0.0.1:5678`, data kept in the `n8n_data` volume |
| `.env.example` → `.env` | API keys and settings (`.env` is git-ignored) |
| `scripts/build_workflow.py` | **Source of the workflow.** Edit this, not the JSON |
| `workflows/tech-to-shorts.json` | Generated workflow, imported into n8n |
| `scripts/setup.sh` | Creates `.env`, starts n8n, builds and imports the workflow |

## Setup

1. `./scripts/setup.sh` (already run once: n8n is up and the workflow is imported).
2. Edit `.env` and fill in:
   - `ANTHROPIC_API_KEY`: from https://console.anthropic.com
   - `FAL_KEY`: from https://fal.ai/dashboard/keys (VEED's API for this is served through fal.ai)
   - optional: `VEED_AVATAR_ID`, `YOUTUBE_PRIVACY`, `YOUTUBE_REGION`, `CLAUDE_MODEL`
3. `docker compose up -d` (restarts n8n with the new env values).
4. Open http://localhost:5678 and create the owner account.
5. **YouTube credential** (one-time, in the UI):
   - In Google Cloud Console, create a project, enable **YouTube Data API v3**, configure the OAuth consent screen (add your Google account as a test user), and create an **OAuth client ID** (Web application) with this redirect URI:
     `http://localhost:5678/rest/oauth2-credential/callback`
   - In n8n, open the workflow, then the **Upload to YouTube** node, then *Create new credential* (YouTube OAuth2 API). Paste the client ID and secret, click *Sign in with Google*, and pick the brand account for **The Tech Voyager** channel.
6. Run it:
   - **Manual:** edit the URLs in the **URL List** node, then click *Execute workflow*.
   - **Form:** activate the workflow, open the **Submit URLs (Form)** node, copy the production URL, and paste URLs (one per line) into the form.

## Notes and limits

- **Script rules** follow the `youtube-video-generation-prompt` skill: one-paragraph summary (110–140 words, roughly 50 s), ending with a like/share/subscribe call to action for The Tech Voyager; an eye-catching title; a short description; and SEO hashtags including #TheTechVoyager and #Shorts. The source site is never mentioned.
- **Model:** `claude-opus-5-5` with server-side refusal fallback enabled (`fallbacks: "default"`). Set `CLAUDE_MODEL` to change it.
- **VEED:** uses `veed/avatars/text-to-video` (talking AI presenter, about $0.35 per video-minute). Use a `*_vertical_*` avatar so the output is 9:16.
- **Privacy defaults to `private`** so you can review each Short before publishing. Because the presenter is AI-generated, turn on YouTube's "altered or synthetic content" disclosure in Studio when you publish.
- **YouTube API quota:** one upload costs 1,600 of the default 10,000 daily units, so about 6 uploads per day.
- **Crawling:** a plain HTTP fetch. Sites behind bot protection (for example Ars Technica returns a CAPTCHA) or JS-only pages are skipped. Article URLs work better than homepages. For homepages, Claude picks the single most interesting story.
- **Changing the workflow:** edit `scripts/build_workflow.py`, then run
  `python3 scripts/build_workflow.py && docker compose exec n8n n8n import:workflow --input=/workflows/tech-to-shorts.json`
  (this overwrites the imported copy; re-select the YouTube credential afterwards if needed). Alternatively, edit in the UI and stop using the script.
- **CLI run:** `docker compose exec n8n n8n execute --id=TechToShorts0001` runs the manual path.

## VEED via browser automation (`VIDEO_ENGINE=browser`)

Instead of the fal.ai API, n8n can have a local service drive veed.io in Firefox using your own VEED account. YouTube upload stays on the official API.

```
n8n (Docker) ──HTTP──▶ browser-service (host, :8765) ──Playwright──▶ Firefox ──▶ veed.io
                ◀── polls status, then downloads the MP4 from the service
```

- `VIDEO_ENGINE=browser` in `.env` turns on this path. `fal` (or unset) uses the API path.
- The service uses Playwright's bundled Firefox with a **saved VEED login** (`browser-service/auth/veed.json`), not your everyday Firefox profile. Firefox locks the profile while it's open, and Playwright can't drive your installed Firefox. You log in once in the recorder window.
- One video renders at a time. Jobs time out after `VEED_JOB_TIMEOUT_MIN` (default 28 minutes). On failure, a screenshot is saved to `browser-service/debug/<job>.png` and the URL is logged as skipped in n8n.
- Requests are protected by `BROWSER_SERVICE_TOKEN`. The service listens on 0.0.0.0:8765 so the container can reach it.

**One-time setup**
1. `browser-service/record.sh`: a Firefox window opens with the Playwright recorder. Log in to VEED, then make one video exactly as you normally would. Paste a placeholder script where the script goes, then export and download it. Close the window.
2. Ask Claude to adapt `browser-service/recordings/veed_recording.py` into `browser-service/veed_flow.py`. Until then, browser jobs fail with "VEED flow not recorded yet".
3. `browser-service/run.sh` starts the service. Keep it running while the workflow runs, and keep your desktop session unlocked if `BROWSER_HEADLESS=false`.

If the VEED session expires, run `record.sh` again just to log in.
