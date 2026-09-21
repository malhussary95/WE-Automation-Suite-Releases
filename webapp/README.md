# WE Automation Tools — Web Launcher

A browser-based replacement for `launcher.py` (the CustomTkinter desktop launcher).

The **UI** is plain HTML/CSS/JS. The **automation logic** (Selenium, Playwright,
NTLM, Excel I/O) cannot run inside a browser, so a small **FastAPI** server wraps
the existing scripts unchanged and streams their logs to the page over WebSocket.

```
Browser (HTML/CSS/JS) <──HTTP/WebSocket──>  FastAPI (server.py)  ──>  existing scripts
```

## Install & run

From the repository root:

```powershell
python -m pip install -r webapp/requirements.txt
python -m uvicorn webapp.server:app --reload --port 8000
```

Then open <http://127.0.0.1:8000>.

> Each tool still needs its own dependencies (selenium, playwright, pandas, …).
> The card shows **Ready** or **Missing: …** based on what is importable.

## What maps to what
| Old (tkinter)            | New (web)                          |
|--------------------------|------------------------------------|
| `launcher.py` window     | `static/index.html` + `app.js`     |
| `PROJECTS` list          | `webapp/tools.py`                  |
| Launch + subprocess      | `POST /api/tools/{id}/run`         |
| Live log textbox         | `WS /ws/logs/{job_id}`             |
| Dependency check         | `GET /api/tools`                   |
| Theme toggle             | `data-theme` + `localStorage`      |

## ECRM has its own full web UI
ECRM was converted from a desktop tool into a real browser page — not just a
launcher card. Open **<http://127.0.0.1:8000/ecrm>** (or click **Open ↗** on the
ECRM card). It offers everything the Tkinter GUI did:

* credentials (saved to `ECRM/credentials.json`, same as the desktop app)
* modes **ORDER / CID / SO / ORD**
* paste values, or upload an Excel file
* all 36 data fields, with search, Select All / Clear All and the 4 presets
* debug mode, live log + progress, **Cancel**, and a **Download Excel** button
* an Extraction History browser over `ECRM/output/`

The desktop window is gone — the ECRM card in `webapp/tools.py` is `type="web"`,
so the launcher navigates to the page instead of spawning `ECRM/main.py`.

How it works: the engine in `ECRM/ecrm_extractor` is **unchanged**. Its “gui”
argument was always just an object with attributes, so `webapp/ecrm_adapter.py`
provides `WebGuiContext`, a headless stand-in, and `webapp/ecrm_routes.py` runs
it on a worker thread, pushing logs/progress to the page over the same
`/ws/logs/{job_id}` WebSocket the other tools use.

## API
### Launcher
| Method | Path                       | Purpose                     |
|--------|----------------------------|-----------------------------|
| GET    | `/api/tools`               | List tools + dep status     |
| GET    | `/api/tools/{id}`          | Single tool detail          |
| POST   | `/api/tools/{id}/run`      | Start a tool `{ mode? }`    |
| POST   | `/api/jobs/{job_id}/stop`  | Stop a running job          |
| GET    | `/api/jobs/{job_id}`       | Job status + replay logs    |
| WS     | `/ws/logs/{job_id}`        | Live log stream             |

### ECRM
| Method | Path                                | Purpose                          |
|--------|-------------------------------------|----------------------------------|
| GET    | `/ecrm`                             | The ECRM web page                |
| GET    | `/api/ecrm/meta`                    | Fields, presets, modes, dep check|
| POST   | `/api/ecrm/upload`                  | Upload an Excel input file       |
| POST   | `/api/ecrm/run`                     | Start an extraction              |
| POST   | `/api/ecrm/jobs/{job_id}/stop`      | Cancel a running extraction      |
| GET    | `/api/ecrm/jobs/{job_id}`           | Job status + replay logs         |
| GET    | `/api/ecrm/jobs/{job_id}/download`  | Download that job's Excel        |
| GET    | `/api/ecrm/history`                 | List previous outputs            |
| GET    | `/api/ecrm/history/{name}`          | Download a previous output       |

## Next steps

The ECRM page is the template for converting the remaining tools:

1. Give each tool a page under `/static/<tool>.html` plus a `<tool>_routes.py`,
   reusing the same job + WebSocket pattern (and the log panel CSS).
2. Replace native tkinter dialogs (e.g. FTTH captcha popup) with web modals —
   the backend returns the captcha image, the page shows it and posts back.
3. Gate file-upload/download endpoints so the browser can pick input Excel files.
