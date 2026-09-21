# Processing Fix V2

This build adds server-side job acceptance logs and a watchdog heartbeat.
If the ECRM engine blocks on session/API/import work, the browser will still show:
- Job accepted
- Worker entered
- Current phase
- A heartbeat every few seconds while no new event arrives
- Real exception type and traceback when the worker fails

Diagnostic endpoint: `/api/ecrm/diagnostic`
