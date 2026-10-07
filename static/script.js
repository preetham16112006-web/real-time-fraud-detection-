const form = document.querySelector('#transaction-form');
const analyzeButton = document.querySelector('#analyze-button');
const formError = document.querySelector('#form-error');
const resultPanel = document.querySelector('#result-panel');
const tbody = document.querySelector('#transaction-rows');
const activityMessage = document.querySelector('#activity-message');
const currency = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 });
let decisionChart;
let riskChart;
let probabilityChart;

const sampleTransactions = {
  safe: {
    amount: 500, transaction_time: '11:20', device_id: 'DEV-KNOWN-4821', is_new_device: false,
    location: 'Tumkur', transactions_last_5min: 1, amount_last_5min: 250,
    average_transaction_amount: 1200, distance_from_usual_location: 4,
  },
  suspicious: {
    amount: 12500, transaction_time: '01:40', device_id: 'DEV-NEW-7724', is_new_device: true,
    location: 'Bengaluru', transactions_last_5min: 4, amount_last_5min: 18000,
    average_transaction_amount: 2200, distance_from_usual_location: 185,
  },
  high: {
    amount: 50000, transaction_time: '02:15', device_id: 'DEV-UNFAMILIAR-1364', is_new_device: true,
    location: 'Mysuru', transactions_last_5min: 3, amount_last_5min: 24000,
    average_transaction_amount: 1000, distance_from_usual_location: 640,
  },
};

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character]);
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}

async function fetchJson(url) {
  const response = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}

function renderStats(stats) {
  setText('stat-total', stats.total_transactions.toLocaleString('en-IN'));
  setText('stat-approved', stats.approved.toLocaleString('en-IN'));
  setText('stat-review', stats.under_review.toLocaleString('en-IN'));
  setText('stat-blocked', stats.blocked.toLocaleString('en-IN'));
  setText('stat-fraud-rate', Number(stats.fraud_percentage).toFixed(1));
  setText('chart-total', `${stats.total_transactions.toLocaleString('en-IN')} total`);
  setText('chart-center-total', stats.total_transactions.toLocaleString('en-IN'));
  setText('legend-approved', stats.approved.toLocaleString('en-IN'));
  setText('legend-review', stats.under_review.toLocaleString('en-IN'));
  setText('legend-blocked', stats.blocked.toLocaleString('en-IN'));

  const values = [stats.approved, stats.under_review, stats.blocked];
  const canvas = document.querySelector('#decision-chart');
  if (!canvas || typeof Chart === 'undefined') return;
  if (decisionChart) {
    decisionChart.data.datasets[0].data = values;
    decisionChart.update();
    return;
  }
  decisionChart = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: ['Approved', 'Review', 'Blocked'],
      datasets: [{ data: values, backgroundColor: ['#3e9b70', '#e1ae46', '#cf6559'], borderWidth: 0, hoverOffset: 4 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '76%',
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (item) => ` ${item.label}: ${item.raw}` } } },
    },
  });
}

function renderRiskCharts(transactions) {
  if (typeof Chart === 'undefined') return;

  const riskCounts = ['LOW', 'MEDIUM', 'HIGH'].map(
    (risk) => transactions.filter((transaction) => transaction.risk_level === risk).length
  );
  const riskCanvas = document.querySelector('#risk-chart');
  if (riskCanvas) {
    if (!riskChart) {
      riskChart = new Chart(riskCanvas, {
        type: 'bar',
        data: {
          labels: ['Low', 'Medium', 'High'],
          datasets: [{ data: riskCounts, backgroundColor: ['#328a61', '#d39a2c', '#c64d42'], borderRadius: 5, barThickness: 24 }],
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { titleFont: { size: 15 }, bodyFont: { size: 15 } } },
          scales: {
            x: { beginAtZero: true, ticks: { precision: 0, font: { size: 14 }, color: '#647168' }, grid: { color: '#e9eee9' } },
            y: { ticks: { font: { size: 16, weight: 'bold' }, color: '#35463b' }, grid: { display: false } },
          },
        },
      });
    } else {
      riskChart.data.datasets[0].data = riskCounts;
      riskChart.update();
    }
  }

  const recent = [...transactions].slice(0, 12).reverse();
  const probabilityCanvas = document.querySelector('#probability-chart');
  if (!probabilityCanvas) return;
  const probabilityData = recent.map((transaction) => Number((transaction.fraud_probability * 100).toFixed(1)));
  const labels = recent.map((transaction) => formatTime(transaction.transaction_time));
  if (!probabilityChart) {
    probabilityChart = new Chart(probabilityCanvas, {
      type: 'line',
      data: {
        labels,
        datasets: [{ data: probabilityData, borderColor: '#1d6a4b', backgroundColor: 'rgba(48, 140, 96, 0.13)', fill: true, tension: 0.28, pointRadius: 4, pointHoverRadius: 6, pointBackgroundColor: '#1d6a4b' }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { titleFont: { size: 14 }, bodyFont: { size: 14 }, callbacks: { label: (item) => ` ${item.raw}%` } } },
        scales: {
          x: { ticks: { maxTicksLimit: 5, font: { size: 12 }, color: '#647168' }, grid: { display: false } },
          y: { min: 0, max: 100, ticks: { stepSize: 50, font: { size: 13 }, color: '#647168', callback: (value) => `${value}%` }, grid: { color: '#e9eee9' } },
        },
      },
    });
  } else {
    probabilityChart.data.labels = labels;
    probabilityChart.data.datasets[0].data = probabilityData;
    probabilityChart.update();
  }
}

function formatTime(value) {
  if (!value) return '—';
  const [hour, minute] = value.split(':').map(Number);
  const suffix = hour >= 12 ? 'PM' : 'AM';
  return `${String(hour % 12 || 12).padStart(2, '0')}:${String(minute).padStart(2, '0')} ${suffix}`;
}

function renderTransactions(transactions) {
  renderRiskCharts(transactions);
  if (!transactions.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No transactions yet. Load a demo or enter a transaction to begin.</td></tr>';
    return;
  }
  if (document.querySelector('#result-status').textContent === 'READY') {
    const latest = transactions[0];
    renderResult({
      transaction_id: latest.transaction_id,
      fraud_probability: latest.fraud_probability,
      risk_level: latest.risk_level,
      decision: latest.decision,
      status: latest.status,
    });
  }
  tbody.innerHTML = transactions.map((item) => {
    const decision = item.decision.toLowerCase();
    const risk = item.risk_level.toLowerCase();
    const status = item.status.toLowerCase();
    return `<tr>
      <td class="transaction-code">${escapeHtml(item.transaction_id)}</td>
      <td class="table-amount">${currency.format(item.amount)}</td>
      <td>${escapeHtml(formatTime(item.transaction_time))}</td>
      <td>${escapeHtml(item.location)}</td>
      <td class="table-probability">${(item.fraud_probability * 100).toFixed(2)}%</td>
      <td><span class="risk-label ${risk}">${escapeHtml(item.risk_level)}</span></td>
      <td><span class="decision-text ${decision}">${escapeHtml(item.decision)}</span></td>
      <td><span class="status-label ${status}">${escapeHtml(item.status)}</span></td>
    </tr>`;
  }).join('');
}

function renderResult(result) {
  const percentage = Number((result.fraud_probability * 100).toFixed(2));
  const decision = result.decision.toLowerCase();
  setText('result-probability', `${percentage.toFixed(2)}%`);
  setText('result-decision', result.decision);
  setText('result-risk', `${result.risk_level} RISK`);
  setText('result-id', result.transaction_id);
  setText('result-status', result.status);
  document.querySelector('#result-decision').className = `decision-pill ${decision}`;
  const fill = document.querySelector('#probability-fill');
  fill.className = decision;
  requestAnimationFrame(() => { fill.style.width = `${percentage}%`; });
  resultPanel.hidden = false;
}

async function refreshDashboard() {
  try {
    const [stats, transactions] = await Promise.all([
      fetchJson('/api/stats'),
      fetchJson('/api/transactions?limit=20'),
    ]);
    renderStats(stats);
    renderTransactions(transactions);
  } catch (error) {
    if (!tbody.children.length || tbody.querySelector('.empty-state')) {
      tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Dashboard data is unavailable. Check that the API is running.</td></tr>';
    }
    console.error('Dashboard refresh failed:', error);
  }
}

function csvCell(value) {
  return `"${String(value ?? '').replaceAll('"', '""')}"`;
}

async function exportTransactionsCsv() {
  const button = document.querySelector('#export-csv-button');
  button.disabled = true;
  try {
    const transactions = await fetchJson('/api/transactions?limit=10000');
    if (!transactions.length) {
      activityMessage.textContent = 'There are no transactions to export yet.';
      activityMessage.hidden = false;
      return;
    }
    const columns = [
      ['Transaction ID', 'transaction_id'], ['Amount (INR)', 'amount'],
      ['Time', 'transaction_time'], ['Location', 'location'],
      ['Fraud Probability (%)', 'fraud_probability'], ['Risk', 'risk_level'],
      ['Decision', 'decision'], ['Status', 'status'], ['Created At (UTC)', 'created_at'],
    ];
    const rows = [
      columns.map(([label]) => csvCell(label)).join(','),
      ...transactions.map((transaction) => columns.map(([, key]) => {
        const value = key === 'fraud_probability'
          ? (Number(transaction[key]) * 100).toFixed(2)
          : transaction[key];
        return csvCell(value);
      }).join(',')),
    ];
    const file = new Blob([`\uFEFF${rows.join('\r\n')}`], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(file);
    const download = document.createElement('a');
    download.href = url;
    download.download = `fraud-transactions-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.append(download);
    download.click();
    download.remove();
    URL.revokeObjectURL(url);
    activityMessage.textContent = `Exported ${transactions.length} transaction${transactions.length === 1 ? '' : 's'} as CSV.`;
    activityMessage.hidden = false;
  } catch (error) {
    activityMessage.textContent = error.message || 'Transaction export failed.';
    activityMessage.hidden = false;
  } finally {
    button.disabled = false;
  }
}

async function clearTransactionHistory() {
  const confirmed = window.confirm(
    'Permanently delete every saved transaction from the local dashboard? The model and dataset will not be changed.'
  );
  if (!confirmed) return;

  const button = document.querySelector('#clear-history-button');
  button.disabled = true;
  try {
    const response = await fetch('/api/transactions', { method: 'DELETE', headers: { Accept: 'application/json' } });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || `Request failed (${response.status})`);
    resultPanel.hidden = true;
    activityMessage.textContent = `Cleared ${result.deleted_count} saved transaction${result.deleted_count === 1 ? '' : 's'}.`;
    activityMessage.hidden = false;
    await refreshDashboard();
  } catch (error) {
    activityMessage.textContent = error.message || 'Could not clear transaction history.';
    activityMessage.hidden = false;
  } finally {
    button.disabled = false;
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  formError.hidden = true;
  analyzeButton.disabled = true;
  analyzeButton.querySelector('span:not(.button-arrow)').textContent = '…';
  const data = new FormData(form);
  const payload = {
    amount: Number(data.get('amount')),
    transaction_time: data.get('transaction_time'),
    device_id: data.get('device_id').trim(),
    is_new_device: data.get('is_new_device') === 'true',
    location: data.get('location').trim(),
    transactions_last_5min: Number(data.get('transactions_last_5min')),
    amount_last_5min: Number(data.get('amount_last_5min')),
    average_transaction_amount: Number(data.get('average_transaction_amount')),
    distance_from_usual_location: Number(data.get('distance_from_usual_location')),
  };
  try {
    const response = await fetch('/api/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) {
      const detail = Array.isArray(body.detail) ? body.detail.map((error) => error.msg).join(' ') : body.detail;
      throw new Error(detail || `Request failed (${response.status})`);
    }
    renderResult(body);
    await refreshDashboard();
  } catch (error) {
    formError.textContent = error.message || 'The transaction could not be analyzed.';
    formError.hidden = false;
  } finally {
    analyzeButton.disabled = false;
    analyzeButton.querySelector('span:not(.button-arrow)').textContent = '⌁';
  }
});

document.querySelectorAll('[data-sample]').forEach((button) => {
  button.addEventListener('click', () => {
    const values = sampleTransactions[button.dataset.sample];
    Object.entries(values).forEach(([name, value]) => {
      const field = form.elements.namedItem(name);
      if (field) field.value = String(value);
    });
    formError.hidden = true;
    form.querySelector('#amount').focus();
  });
});

document.querySelector('#refresh-button').addEventListener('click', refreshDashboard);
document.querySelector('#export-csv-button').addEventListener('click', exportTransactionsCsv);
document.querySelector('#export-pdf-button').addEventListener('click', () => window.print());
document.querySelector('#clear-history-button').addEventListener('click', clearTransactionHistory);
document.querySelector('#dismiss-result').addEventListener('click', () => { resultPanel.hidden = true; });
setText('current-date', new Intl.DateTimeFormat('en', { dateStyle: 'medium' }).format(new Date()));

fetchJson('/api/model-metrics').then((metrics) => {
  setText('model-name', metrics.model_name);
  setText('sidebar-model-name', metrics.model_name.replace(' Classifier', ''));
  setText('training-rows', Number(metrics.training_rows).toLocaleString('en-IN'));
  setText('metric-accuracy', `${(metrics.accuracy * 100).toFixed(1)}%`);
  setText('metric-precision', `${(metrics.precision * 100).toFixed(1)}%`);
  setText('metric-recall', `${(metrics.recall * 100).toFixed(1)}%`);
  setText('metric-f1', `${(metrics.f1_score * 100).toFixed(1)}%`);
}).catch((error) => console.error('Model metrics unavailable:', error));

refreshDashboard();
window.setInterval(refreshDashboard, 10_000);