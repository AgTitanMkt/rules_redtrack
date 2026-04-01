// ─── Monitoring ─────────────────────────────────────────────────
async function runMonitoring() {
  const fb = document.getElementById('monitor-feedback');
  if (!fb) return;
  fb.className = 'feedback loading';
  fb.textContent = 'Running monitoring...';
  try {
    const resp = await fetch('/monitor/run', { method: 'POST' });
    const data = await resp.json();
    if (!data.ok) throw new Error('Failed');
    const s = data.summary;
    fb.className = 'feedback ok';
    fb.textContent = `Done — ${s.total} objects | ${s.matched} matched | ${s.acted} acted | source: ${s.source}`;
    setTimeout(() => window.location.reload(), 1200);
  } catch (err) {
    fb.className = 'feedback error';
    fb.textContent = `Error: ${err.message}`;
  }
}

// ─── Manual Pause ───────────────────────────────────────────────
async function pauseObject(objectId, objectName, objectType, channel, cost, platformId) {
  if (!confirm(`Pause "${objectName}"?`)) return;
  try {
    const resp = await fetch(`/api/objects/${objectId}/pause`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ object_name: objectName, object_type: objectType, traffic_channel: channel, cost, platform_id: platformId }),
    });
    const data = await resp.json();
    if (!data.ok) throw new Error(data.error || 'Failed');
    alert(`Result: ${data.status}`);
    window.location.reload();
  } catch (err) { alert(`Error: ${err.message}`); }
}

// ─── Scheduler ──────────────────────────────────────────────────
let schedulerRunning = false;

async function toggleScheduler() {
  const interval = document.getElementById('sched-interval')?.value || 5;
  try {
    if (schedulerRunning) {
      await fetch('/api/scheduler/stop', { method: 'POST' });
      schedulerRunning = false;
    } else {
      await fetch('/api/scheduler/start', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interval_minutes: parseInt(interval) }),
      });
      schedulerRunning = true;
    }
    updateSchedulerUI();
  } catch (err) { console.error('Scheduler error:', err); }
}

function updateSchedulerUI() {
  const btn = document.getElementById('sched-toggle-btn');
  const dot = document.getElementById('sched-dot');
  const label = document.getElementById('sched-label');
  if (!btn) return;
  if (schedulerRunning) {
    btn.textContent = 'Stop'; btn.className = 'btn btn-danger-outline btn-sm';
    if (dot) dot.className = 'status-dot dot-live';
    if (label) label.textContent = 'Scheduler ON';
  } else {
    btn.textContent = 'Start'; btn.className = 'btn btn-outline';
    if (dot) dot.className = 'status-dot dot-off';
    if (label) label.textContent = 'Scheduler OFF';
  }
}

async function checkSchedulerStatus() {
  try {
    const resp = await fetch('/api/scheduler/status');
    const data = await resp.json();
    schedulerRunning = data.running;
    updateSchedulerUI();
  } catch (e) {}
}

document.addEventListener('DOMContentLoaded', checkSchedulerStatus);
