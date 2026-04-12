let currentData = [];
let currentFilter = 'all';
let tempChart = null, rainChart = null;
let currentFile = null;
let dataSource = null; // 'sample' or 'file'

// ─── DRAG & DROP ───────────────────────────────────────────────
const dropzone = document.getElementById('dropzone');
const csvInput = document.getElementById('csv-file');
const fileNameEl = document.getElementById('file-name');

dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
dropzone.addEventListener('drop', e => {
  e.preventDefault(); dropzone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file && file.name.endsWith('.csv')) setFile(file);
});
csvInput.addEventListener('change', e => { if (e.target.files[0]) setFile(e.target.files[0]); });

function setFile(file) {
  currentFile = file;
  dataSource = 'file';
  fileNameEl.textContent = '✓ ' + file.name + ' (' + (file.size / 1024).toFixed(1) + ' KB)';
  fileNameEl.classList.remove('hidden');
}

// ─── BUTTONS ───────────────────────────────────────────────────
document.getElementById('sample-btn').addEventListener('click', () => {
  dataSource = 'sample';
  currentFile = null;
  fileNameEl.classList.add('hidden');
  fetchSample();
});

document.getElementById('run-btn').addEventListener('click', () => {
  if (dataSource === 'sample') fetchSample();
  else if (dataSource === 'file' && currentFile) uploadFile();
  else if (currentFile) uploadFile();
  else fetchSample(); // default to sample if nothing selected
});

// ─── FILTER BUTTONS ────────────────────────────────────────────
document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentFilter = btn.dataset.filter;
    applyFilter();
  });
});

function applyFilter() {
  document.querySelectorAll('#data-tbody tr').forEach(row => {
    const isAnomaly = row.classList.contains('is-anomaly');
    let show = true;
    if (currentFilter === 'anomaly') show = isAnomaly;
    if (currentFilter === 'normal') show = !isAnomaly;
    row.classList.toggle('hidden-row', !show);
  });
}

// ─── API CALLS ─────────────────────────────────────────────────
function getParams() {
  return {
    temp_thresh: document.getElementById('temp-thresh').value || 3,
    rain_thresh: document.getElementById('rain-thresh').value || 20,
    mode: document.getElementById('avg-mode').value
  };
}

function fetchSample() {
  const p = getParams();
  showLoader(true);
  hideError();
  const url = `/api/sample?temp_thresh=${p.temp_thresh}&rain_thresh=${p.rain_thresh}&mode=${p.mode}`;
  fetch(url)
    .then(r => r.json())
    .then(data => {
      showLoader(false);
      if (data.ok) renderResults(data.stats, data.records);
      else showError(data.error);
    })
    .catch(e => { showLoader(false); showError('Network error: ' + e.message); });
}

function uploadFile() {
  const p = getParams();
  const form = new FormData();
  form.append('file', currentFile);
  form.append('temp_thresh', p.temp_thresh);
  form.append('rain_thresh', p.rain_thresh);
  form.append('mode', p.mode);
  showLoader(true);
  hideError();
  fetch('/api/upload', { method: 'POST', body: form })
    .then(r => r.json())
    .then(data => {
      showLoader(false);
      if (data.ok) renderResults(data.stats, data.records);
      else showError(data.error);
    })
    .catch(e => { showLoader(false); showError('Network error: ' + e.message); });
}

// ─── RENDER ────────────────────────────────────────────────────
function renderResults(stats, records) {
  currentData = records;

  // Metrics
  document.getElementById('m-total').textContent = stats.total;
  document.getElementById('m-anomalies').textContent = stats.anomalies;
  document.getElementById('m-pct').textContent = stats.anomaly_pct + '% of data';
  document.getElementById('m-avg-temp').textContent = stats.avg_temp;
  document.getElementById('m-avg-rain').textContent = stats.avg_rain;

  renderTable(records);
  renderCharts(records);

  const sec = document.getElementById('results');
  sec.classList.remove('hidden');
  sec.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderTable(records) {
  const tbody = document.getElementById('data-tbody');
  tbody.innerHTML = records.map(r => `
    <tr class="${r.is_anomaly ? 'is-anomaly' : ''}">
      <td>${r.idx}</td>
      <td>${r.month}${r.year ? ' ' + r.year : ''}</td>
      <td>${r.temperature}</td>
      <td class="${r.temp_diff > 0 ? 'diff-pos' : 'diff-neg'}">${r.temp_diff >= 0 ? '+' : ''}${r.temp_diff}</td>
      <td>${r.rainfall}</td>
      <td class="${r.rain_diff > 0 ? 'diff-pos' : 'diff-neg'}">${r.rain_diff >= 0 ? '+' : ''}${r.rain_diff}</td>
      <td><span class="badge ${r.is_anomaly ? 'badge-flag' : 'badge-ok'}">${r.is_anomaly ? '⚠ Flagged' : '✓ Normal'}</span></td>
    </tr>
  `).join('');
  applyFilter();
}

function renderCharts(records) {
  const labels = records.map((r, i) => r.month + (r.year ? " '" + String(r.year).slice(2) : ''));
  const gridColor = 'rgba(255,255,255,0.05)';
  const textColor = '#7b7f96';

  const baseOpts = {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#111318',
        titleColor: '#e2e4ed', bodyColor: '#7b7f96',
        borderColor: 'rgba(255,255,255,0.1)', borderWidth: 1,
        padding: 10
      }
    },
    scales: {
      x: { ticks: { color: textColor, font: { size: 10, family: 'JetBrains Mono' }, maxRotation: 45 }, grid: { color: gridColor } },
      y: { ticks: { color: textColor, font: { size: 10 } }, grid: { color: gridColor } }
    }
  };

  if (tempChart) tempChart.destroy();
  if (rainChart) rainChart.destroy();

  const tc = document.getElementById('temp-chart').getContext('2d');
  tempChart = new Chart(tc, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Temperature',
          data: records.map(r => r.temperature),
          borderColor: '#4a90e2',
          backgroundColor: 'rgba(74,144,226,0.07)',
          fill: true, tension: 0.35,
          pointBackgroundColor: records.map(r => r.is_anomaly ? '#e05c5c' : '#4a90e2'),
          pointRadius: records.map(r => r.is_anomaly ? 7 : 3),
          pointHoverRadius: 9
        },
        {
          label: 'Avg baseline',
          data: records.map(r => r.avg_temp),
          borderColor: '#3f4358', borderDash: [5, 5],
          backgroundColor: 'transparent', pointRadius: 0, tension: 0
        }
      ]
    },
    options: baseOpts
  });

  const rc = document.getElementById('rain-chart').getContext('2d');
  rainChart = new Chart(rc, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Rainfall',
          data: records.map(r => r.rainfall),
          backgroundColor: records.map(r => r.is_anomaly ? 'rgba(224,92,92,0.7)' : 'rgba(46,204,138,0.6)'),
          borderColor: records.map(r => r.is_anomaly ? '#e05c5c' : '#2ecc8a'),
          borderWidth: 1, borderRadius: 4
        },
        {
          label: 'Avg baseline',
          data: records.map(r => r.avg_rain),
          type: 'line',
          borderColor: '#3f4358', borderDash: [5, 5],
          backgroundColor: 'transparent', pointRadius: 0, tension: 0
        }
      ]
    },
    options: baseOpts
  });
}

// ─── UTILS ─────────────────────────────────────────────────────
function showLoader(show) { document.getElementById('loader').classList.toggle('hidden', !show); }
function showError(msg) {
  const el = document.getElementById('error-box');
  el.textContent = '⚠ ' + msg;
  el.classList.remove('hidden');
}
function hideError() { document.getElementById('error-box').classList.add('hidden'); }
