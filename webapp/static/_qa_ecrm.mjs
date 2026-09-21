export default async function run(page, ui) {
  // Search filters the field grid.
  await page.fill('#fieldSearch', 'CID');
  await page.waitForTimeout(200);
  const filtered = await page.evaluate(() =>
    document.querySelectorAll('#fieldsGrid .field-cell').length);

  await page.fill('#fieldSearch', '');
  await page.waitForTimeout(200);

  // Select All -> count should equal 36.
  const buttons = await ui.snapshot();
  const selectAllRef = buttons.match(/@(e\d+) button "Select All"/)?.[1];
  if (selectAllRef) await ui.click(selectAllRef);
  const allCount = await page.evaluate(() =>
    document.querySelector('#fieldsCount').textContent);

  // Switch to CID mode.
  await page.evaluate(() => {
    const tab = [...document.querySelectorAll('.mode-tab')].find(t => t.dataset.mode === 'CID');
    tab.click();
  });
  const activeMode = await page.evaluate(() =>
    document.querySelector('.mode-tab.active').dataset.mode);
  const placeholder = await page.evaluate(() =>
    document.querySelector('#directValues').placeholder);

  // Typing values updates the "N added" pill.
  await page.fill('#directValues', 'CID-1, CID-2\nCID-3');
  await page.waitForTimeout(150);
  const directCount = await page.evaluate(() =>
    document.querySelector('#directCount').textContent);

  // Opening presets shows a modal with the 4 presets.
  await page.evaluate(() => {
    [...document.querySelectorAll('.side-item')].find(b => b.dataset.nav === 'presets').click();
  });
  await page.waitForTimeout(300);
  const presetItems = await page.evaluate(() =>
    document.querySelectorAll('#modalBody .preset-item strong').length);
  const modalOpen = await page.evaluate(() =>
    !document.querySelector('#modal').classList.contains('hidden'));

  return {
    filteredCID: filtered, selectAllCount: allCount, activeMode, placeholder,
    directCount, presetItems, modalOpen
  };
}
