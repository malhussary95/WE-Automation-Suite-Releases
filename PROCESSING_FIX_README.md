# WE ECRM Web — Processing Diagnostic/Progress Fix

This build fixes the browser job state so extraction does not appear frozen simply because WebSocket events were missed.

Changes:
- Replay all job logs immediately after Start Extraction.
- Poll `/api/ecrm/jobs/{job_id}` every second as a fallback.
- Show extraction phase: Reading Input / Resolving Items / Creating Session / Processing / Completed.
- Add explicit backend logs before and after session creation and major extraction stages.
- Keep real progress and output download behavior.
- Keep the existing Credentials and no-cache web UI behavior.

Run the server on the same port used by your launcher, or use the provided launcher.
