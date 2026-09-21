# TODO - Smart Chat Enhancements (ECRM)

- [x] Step 1: Update `ECRM/ecrm_extractor/gui.py` - add language detection helper (Arabic/English/Egyptian colloquial).
- [ ] Step 2: Update AI prompt(s) to request `friendly_reply` in the detected language while keeping JSON-only schema.
- [ ] Step 3: Add local fast-path friendly responses (greetings / simple intents) using detected language to improve performance.
- [ ] Step 4: Ensure JSON parsing remains robust (extract first JSON object only).
- [ ] Step 5: Update any UI placeholder/welcome messages if they should reflect language.
- [ ] Step 6: Manual test scenarios: 

  - [ ] Arabic Fusha input.
  - [ ] English input.
  - [ ] Egyptian colloquial input.
  - [ ] Ensure mode/fields/values/wants_to_save are applied correctly.



## V4 changes
- Root URL opens ECRM directly at http://127.0.0.1:8010/
- ECRM credentials are locked to the Windows/domain account running the backend.
- Server rejects attempts to submit a different ECRM username.
