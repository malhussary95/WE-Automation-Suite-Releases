export default async function run(page, ui) {
  // 1) Click the ECRM "Open ↗" button on the launcher and confirm navigation.
  const snap = await ui.snapshot();
  const openRef = snap.match(/@(e\d+) button "Open ↗"/)?.[1];
  if (!openRef) return { error: 'no Open button', snap };
  await Promise.all([
    page.waitForURL('**/ecrm', { timeout: 8000 }).catch(() => { }),
    ui.click(openRef),
  ]);
  const onEcrm = page.url().endsWith('/ecrm');

  // 2) Start a real extraction with dummy creds — proves the whole pipeline.
  await page.fill('#username', 'test.user');
  await page.fill('#password', 'x');
  await page.evaluate(() => {
    const tab = [...document.querySelectorAll('.mode-tab')].find(t => t.dataset.mode === 'ORDER');
    tab.click();
    document.querySelector('#directValues').value = 'ORD-000';
    document.querySelector('#directValues').dispatchEvent(new Event('input'));
  });
  // Tick two fields.
  await page.evaluate(() => {
    const cells = [...document.querySelectorAll('#fieldsGrid .field-cell')];
    const wanted = ['Order', 'CST Name'];
    cells.forEach((c) => {
      const label = c.querySelector('span').textContent;
      if (wanted.includes(label)) c.querySelector('input').click();
    });
  });

  const startRef = await ui.snapshot().then(s => s.match(/@(e\d+) button "🚀 Start Extraction/)?.[1]);
  if (startRef) await ui.click(startRef);

  // The job should begin streaming logs over the WebSocket.
  await page.waitForTimeout(4000);
  const state = await page.evaluate(() => ({
    logVisible: !document.querySelector('#logPanel').classList.contains('hidden'),
    logLines: document.querySelectorAll('#logOutput .log-line').length,
    jobStatus: document.querySelector('#logJobStatus').textContent,
    cancelEnabled: !document.querySelector('#cancelBtn').disabled,
  }));

  // 3) Cancel to exercise the stop endpoint, then read final status.
  if (state.cancelEnabled) {
    await page.evaluate(() => document.querySelector('#cancelBtn').click());
    await page.waitForTimeout(2500);
  }
  const after = await page.evaluate(() => ({
    jobStatus: document.querySelector('#logJobStatus').textContent,
    startEnabled: !document.querySelector('#startBtn').disabled,
  }));

  return { onEcrm, ...state, after };
}
