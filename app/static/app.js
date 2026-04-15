const tableBody = document.querySelector('#decisions-table tbody');
const statusNode = document.getElementById('status');
const createForm = document.getElementById('create-form');
const filtersForm = document.getElementById('filters-form');

function setStatus(text, isError = false) {
  statusNode.textContent = text;
  statusNode.style.color = isError ? '#c62828' : '#546e7a';
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function normalizeList(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.decisions)) return payload.decisions;
  return [];
}

function renderRows(items) {
  if (!items.length) {
    tableBody.innerHTML = '<tr><td colspan="8">No active decisions</td></tr>';
    return;
  }

  tableBody.innerHTML = items
    .map((item) => {
      const id = item.id ?? '';
      const value = escapeHtml(item.value);
      const scope = escapeHtml(item.scope);
      const type = escapeHtml(item.type);
      const origin = escapeHtml(item.origin);
      const scenario = escapeHtml(item.scenario);
      const until = escapeHtml(item.until ?? item.expiration ?? '');
      const action = id
        ? `<button data-id="${id}" class="delete-btn secondary">Delete</button>`
        : '';

      return `
        <tr>
          <td>${id}</td>
          <td>${value}</td>
          <td>${scope}</td>
          <td>${type}</td>
          <td>${origin}</td>
          <td>${scenario}</td>
          <td>${until}</td>
          <td>${action}</td>
        </tr>
      `;
    })
    .join('');
}

async function fetchDecisions() {
  const formData = new FormData(filtersForm);
  const params = new URLSearchParams();

  for (const [key, rawValue] of formData.entries()) {
    const value = String(rawValue).trim();
    if (!value) continue;
    params.set(key, value);
  }

  setStatus('Loading decisions...');
  try {
    const response = await fetch(`/api/decisions?${params.toString()}`);
    if (!response.ok) {
      throw new Error(await response.text());
    }

    const payload = await response.json();
    const decisions = normalizeList(payload);
    renderRows(decisions);
    setStatus(`Loaded ${decisions.length} decision(s).`);
  } catch (error) {
    renderRows([]);
    setStatus(`Failed to load decisions: ${error.message}`, true);
  }
}

createForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(createForm);
  const payload = Object.fromEntries(formData.entries());

  setStatus('Creating decision...');
  try {
    const response = await fetch('/api/decisions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(await response.text());
    }

    createForm.reset();
    createForm.querySelector('input[name="scope"]').value = 'ip';
    createForm.querySelector('input[name="type"]').value = 'ban';
    createForm.querySelector('input[name="duration"]').value = '4h';
    setStatus('Decision created.');
    await fetchDecisions();
  } catch (error) {
    setStatus(`Failed to create decision: ${error.message}`, true);
  }
});

filtersForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  await fetchDecisions();
});

tableBody.addEventListener('click', async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) return;
  if (!target.classList.contains('delete-btn')) return;

  const id = target.dataset.id;
  if (!id) return;
  if (!window.confirm(`Delete decision #${id}?`)) return;

  setStatus(`Deleting decision #${id}...`);
  try {
    const response = await fetch(`/api/decisions/${id}`, { method: 'DELETE' });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    setStatus(`Decision #${id} deleted.`);
    await fetchDecisions();
  } catch (error) {
    setStatus(`Failed to delete decision #${id}: ${error.message}`, true);
  }
});

fetchDecisions();
