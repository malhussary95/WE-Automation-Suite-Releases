
# WE ECRM Extractor — Web Connected Edition

The desktop GUI and browser UI now share the same ECRM backend.

## Desktop

```powershell
python main.py
```

`main.py` starts the bundled FastAPI server on:

`http://127.0.0.1:8000`

The desktop GUI uses the Web API for extraction by default.

## Browser

Open:

`http://127.0.0.1:8000/ecrm`

The browser UI and desktop GUI use the same backend and ECRM extraction engine.

## Architecture

```text
Desktop GUI ──HTTP──> FastAPI ──> ECRM runner
Browser UI  ──HTTP──> FastAPI ──> ECRM runner
                     │
                     └── WebSocket logs
```

This means extraction logic is no longer duplicated between the desktop GUI and the web frontend.
