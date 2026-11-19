/* Progressive enhancement: source approvals do not navigate or reset the scroll.
   Plain HTML forms still work if JavaScript is disabled. */
(() => {
  const feedback = document.getElementById('source-action-feedback');
  if (!feedback) return;

  const updateFrom = (next, elementId) => {
    const oldElement = document.getElementById(elementId);
    const nextElement = next.getElementById(elementId);
    if (oldElement && nextElement) oldElement.replaceWith(nextElement);
  };

  document.addEventListener('submit', async (event) => {
    const form = event.target.closest('form[data-source-action]');
    if (!form) return;
    event.preventDefault();

    const kind = form.dataset.sourceAction;
    const category = new URLSearchParams(location.search).get('category') || 'Customers';
    const count = Number(form.dataset.count || 0);
    if (kind === 'bulk' && !window.confirm(
      `Approve ${count} proposed sources in ${category}?\n\n` +
      'Only approve sources you have reviewed for relevance and access rules. ' +
      'This does not start monitoring.'
    )) return;

    const sourceCard = kind === 'single' ? form.closest('.source-entry') : null;
    const sourceId = sourceCard ? sourceCard.id : '';
    const submitter = event.submitter;
    const status = submitter && submitter.name === 'status' ? submitter.value : '';
    const payload = new FormData(form);
    if (submitter && submitter.name) payload.append(submitter.name, submitter.value);
    const beforeY = window.scrollY;
    const buttons = Array.from(form.querySelectorAll('button'));
    buttons.forEach(b => { b.disabled = true; });
    feedback.hidden = false;
    feedback.classList.remove('source-action-error');
    feedback.textContent = 'Saving source approval…';

    try {
      const response = await fetch(form.action, {
        method: 'POST', body: payload, credentials: 'same-origin', redirect: 'follow',
        headers: { 'Accept': 'text/html' }
      });
      if (!response.ok) throw new Error(`Server returned HTTP ${response.status}`);
      if (!response.url.includes('tab=sources')) throw new Error('Unexpected response from the source manager');
      const html = await response.text();
      const next = new DOMParser().parseFromString(html, 'text/html');
      if (!next.getElementById('source-manager-panel')) throw new Error('Source list was not returned');

      // Update the selected row only for approve/pause to preserve expanded
      // histories and every other card's on-screen position.
      const nextRow = sourceId ? next.getElementById(sourceId) : null;
      if (sourceCard && nextRow && status !== 'removed' && !form.closest('details')) {
        sourceCard.replaceWith(nextRow);
        updateFrom(next, 'source-category-heading');
      } else {
        updateFrom(next, 'source-manager-panel');
      }
      updateFrom(next, 'source-bulk-actions');
      updateFrom(next, 'pipeline-status');
      updateFrom(next, 'source-tab-count-' + category);
      // No navigation: the position remains the same even after a bulk update.
      window.scrollTo(0, beforeY);
      feedback.hidden = false;
      feedback.textContent = kind === 'bulk'
        ? `${count} proposed ${category.toLowerCase()} sources approved. Run monitoring to collect evidence.`
        : status === 'approved' ? 'Source approved.'
        : status === 'removed' ? 'Source removed.'
        : status === 'proposed' ? 'Source moved back to proposed.'
        : 'Source updated.';
    } catch (error) {
      buttons.forEach(b => { b.disabled = false; });
      feedback.classList.add('source-action-error');
      feedback.textContent = `Couldn't update sources: ${error.message}. You can try again.`;
    }
  });
})();
