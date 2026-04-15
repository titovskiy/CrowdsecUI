const tableBody = document.querySelector('#decisions-table tbody');
const statusNode = document.getElementById('status');
const createForm = document.getElementById('create-form');
const filtersForm = document.getElementById('filters-form');
const refreshMetricsBtn = document.getElementById('refresh-metrics-btn');

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

async function responseError(response) {
  const body = await response.text();
  if (!body) return `${response.status} ${response.statusText}`;
  try {
    const json = JSON.parse(body);
    if (json?.detail) return String(json.detail);
  } catch (_e) {
    // Keep raw text fallback.
  }
  return body;
}

function formatDateTime(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return escapeHtml(value);
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

function renderMetricSummary(summary) {
  const metrics = document.querySelectorAll('[data-metric]');
  for (const node of metrics) {
    const key = node.dataset.metric;
    const value = summary?.[key];
    node.textContent = value ?? '-';
  }
}

async function fetchMetricsSummary() {
  try {
    const response = await fetch('/api/metrics/summary');
    if (!response.ok) {
      throw new Error(await responseError(response));
    }
    const payload = await response.json();
    renderMetricSummary(payload.summary ?? {});
    if (payload.available === false) {
      setStatus(`Metrics unavailable: ${payload.detail}`);
    } else if (payload.source) {
      setStatus(`Metrics source: ${payload.source}`);
    }
  } catch (error) {
    renderMetricSummary({});
    setStatus(`Failed to load metrics: ${error.message}`, true);
  }
}

function parseDurationMs(duration) {
  if (!duration) return null;
  const source = String(duration).trim();
  const re = /(\d+)(ns|us|µs|ms|s|m|h|d|w)/g;
  const unitMs = {
    ns: 1 / 1e6,
    us: 1 / 1e3,
    'µs': 1 / 1e3,
    ms: 1,
    s: 1000,
    m: 60 * 1000,
    h: 60 * 60 * 1000,
    d: 24 * 60 * 60 * 1000,
    w: 7 * 24 * 60 * 60 * 1000,
  };

  let total = 0;
  let matched = false;
  let m;
  while ((m = re.exec(source)) !== null) {
    matched = true;
    total += Number(m[1]) * unitMs[m[2]];
  }
  return matched ? total : null;
}

function computeCreated(item) {
  const explicitCreated = item.created_at ?? item.start_at ?? item.created;
  if (explicitCreated) return explicitCreated;

  const untilRaw = item.until ?? item.expiration ?? item.expires_at;
  if (!untilRaw || !item.duration) return '';

  const untilDate = new Date(untilRaw);
  const durationMs = parseDurationMs(item.duration);
  if (Number.isNaN(untilDate.getTime()) || durationMs === null) return '';

  return new Date(untilDate.getTime() - durationMs).toISOString();
}

function renderRows(items) {
  if (!items.length) {
    tableBody.innerHTML = '<tr><td colspan="9">No active decisions</td></tr>';
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
      const created = formatDateTime(computeCreated(item));
      const until = formatDateTime(item.until ?? item.expiration ?? item.expires_at);
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
          <td>${created}</td>
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
      throw new Error(await responseError(response));
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
      throw new Error(await responseError(response));
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
      throw new Error(await responseError(response));
    }
    setStatus(`Decision #${id} deleted.`);
    await fetchDecisions();
  } catch (error) {
    setStatus(`Failed to delete decision #${id}: ${error.message}`, true);
  }
});

if (refreshMetricsBtn) {
  refreshMetricsBtn.addEventListener('click', async () => {
    await fetchMetricsSummary();
  });
}

fetchMetricsSummary();
fetchDecisions();
