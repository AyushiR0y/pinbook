/* ═══════════════════════════════════════════════════════════════
   PINBOOK — Frontend Application
   Author: Enterprise Design System
   API Base: relative (same origin as FastAPI backend)
═══════════════════════════════════════════════════════════════ */

'use strict';

// ── Config ────────────────────────────────────────────────────
const API_BASE = '';  // Same origin — FastAPI at /api/...
const KYL_URL  = 'https://knowyourleads-1.onrender.com';

// ── State ─────────────────────────────────────────────────────
const state = {
  pin: '',
  locationData: null,  // { lat, lng, district, state, officename, address }
  demoData: null,      // from /api/search/{pin}
  selectedModules: new Set(),
  chartsRendered: {},
  bizCoords: null,
};

// ── DOM References ─────────────────────────────────────────────
const $ = id => document.getElementById(id);

// ═══════════════════════════════════════════════════════════════
//  SCREEN NAVIGATION
// ═══════════════════════════════════════════════════════════════
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => {
    s.classList.remove('active');
    s.style.display = 'none';
  });
  const target = document.getElementById(id);
  if (target) {
    // Landing needs flex, others block
    target.style.display = id === 'screen-landing' ? 'flex' : 'block';
    // micro delay for CSS transition
    requestAnimationFrame(() => target.classList.add('active'));
    window.scrollTo(0, 0);
  }
}

// ═══════════════════════════════════════════════════════════════
//  TOAST
// ═══════════════════════════════════════════════════════════════
let toastTimer = null;
function showToast(msg, duration = 3000) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), duration);
}

// ═══════════════════════════════════════════════════════════════
//  UTILS
// ═══════════════════════════════════════════════════════════════
function formatNum(n) {
  if (!n && n !== 0) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return n.toString();
}

function formatPct(n) {
  if (n === undefined || n === null) return '—';
  return n.toFixed(1) + '%';
}

function titleCase(str) {
  return str.replace(/\b\w/g, c => c.toUpperCase()).toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
}

function getInitials(name) {
  return (name || '?').split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();
}

// Destroy chart safely before re-creating
function destroyChart(id) {
  const existing = Chart.getChart(id);
  if (existing) existing.destroy();
}

// ═══════════════════════════════════════════════════════════════
//  SCREEN 1 — LANDING
// ═══════════════════════════════════════════════════════════════
(function initLanding() {
  const pinInput  = $('pin-input');
  const btnAnalyze = $('btn-analyze');
  const pinError   = $('pin-error');
  const pinErrTxt  = $('pin-error-text');

  function validate(val) {
    return /^\d{6}$/.test(val);
  }

  function onInput() {
    const val = pinInput.value.replace(/\D/g, '').slice(0, 6);
    pinInput.value = val;

    if (val.length === 0) {
      pinInput.classList.remove('input-error-state');
      pinError.classList.remove('visible');
      btnAnalyze.disabled = true;
      return;
    }

    if (!validate(val)) {
      pinInput.classList.add('input-error-state');
      pinError.classList.add('visible');
      pinErrTxt.textContent = val.length < 6
        ? `PIN must be 6 digits (${val.length}/6 entered)`
        : 'Please enter a valid 6-digit numeric PIN.';
      btnAnalyze.disabled = true;
    } else {
      pinInput.classList.remove('input-error-state');
      pinError.classList.remove('visible');
      btnAnalyze.disabled = false;
    }
  }

  pinInput.addEventListener('input', onInput);

  pinInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !btnAnalyze.disabled) startAnalysis();
  });

  btnAnalyze.addEventListener('click', startAnalysis);

  async function startAnalysis() {
    const val = pinInput.value.trim();
    if (!validate(val)) return;

    state.pin = val;
    btnAnalyze.disabled = true;
    btnAnalyze.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Searching…';

    try {
      const res = await fetch(`${API_BASE}/api/search/${val}`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      state.locationData = data.location;
      state.demoData     = data.demographics;

      // Update selection screen location pill
      const locStr = [
        titleCase(data.location.district),
        titleCase(data.location.state)
      ].filter(Boolean).join(', ');

      $('selection-location-text').textContent = locStr || `PIN ${val}`;
      $('header-pin-display').textContent = val;

      showScreen('screen-selection');
    } catch (err) {
      console.error(err);
      pinInput.classList.add('input-error-state');
      pinError.classList.add('visible');
      pinErrTxt.textContent = err.message || 'Could not find this PIN code. Please try again.';
    } finally {
      btnAnalyze.disabled = false;
      btnAnalyze.innerHTML = '<i class="fa-solid fa-chart-mixed"></i> Analyze Location';
    }
  }
})();

// ═══════════════════════════════════════════════════════════════
//  SCREEN 2 — SELECTION
// ═══════════════════════════════════════════════════════════════
(function initSelection() {
  const cards   = document.querySelectorAll('.insight-card');
  const btnCont = $('btn-continue');
  const btnBack = $('btn-back-landing');

  cards.forEach(card => {
    card.addEventListener('click', () => toggleCard(card));
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') toggleCard(card);
    });
  });

  function toggleCard(card) {
    const module = card.dataset.module;
    if (state.selectedModules.has(module)) {
      state.selectedModules.delete(module);
      card.classList.remove('selected');
      card.setAttribute('aria-checked', 'false');
    } else {
      state.selectedModules.add(module);
      card.classList.add('selected');
      card.setAttribute('aria-checked', 'true');
    }
    btnCont.disabled = state.selectedModules.size === 0;
  }

  btnBack.addEventListener('click', () => {
    state.selectedModules.clear();
    cards.forEach(c => { c.classList.remove('selected'); c.setAttribute('aria-checked', 'false'); });
    btnCont.disabled = true;
    showScreen('screen-landing');
  });

  btnCont.addEventListener('click', () => {
    if (state.selectedModules.size === 0) return;
    initDashboard();
    showScreen('screen-dashboard');
  });

  // Home button
  $('btn-home').addEventListener('click', () => {
    state.selectedModules.clear();
    cards.forEach(c => { c.classList.remove('selected'); c.setAttribute('aria-checked', 'false'); });
    btnCont.disabled = true;
    showScreen('screen-landing');
  });
})();

// ═══════════════════════════════════════════════════════════════
//  SCREEN 3 — DASHBOARD
// ═══════════════════════════════════════════════════════════════
function renderMap(lat, lng) {
  const mapContainer = document.getElementById('map-container');

  mapContainer.innerHTML = `
    <iframe
      width="100%"
      height="100%"
      frameborder="0"
      style="border:0"
      referrerpolicy="no-referrer-when-downgrade"
      src="https://www.openstreetmap.org/export/embed.html?bbox=${lng-0.02},${lat-0.02},${lng+0.02},${lat+0.02}&layer=mapnik&marker=${lat},${lng}">
    </iframe>
  `;
}
async function initDashboard() {
  const loc = state.locationData;
  const pin = state.pin;

  // Hero
  $('dash-pin-value').textContent = pin;
  $('breadcrumb-pin').textContent = `PIN ${pin}`;

  // Road/area: strip postal suffixes (S.O, B.O, H.O) from officename
  const rawOffice = (loc.officename || '').replace(/\s*(s\.?o\.?|b\.?o\.?|h\.?o\.?)\s*$/i, '').trim();
  $('dash-road').textContent = titleCase(rawOffice);
  $('dash-city').textContent = titleCase(loc.district);
  $('dash-state').textContent = titleCase(loc.state);

  // Meta tags
  const tags = $('dash-meta-tags');
  tags.innerHTML = '';
  if (state.selectedModules.has('demographics')) tags.innerHTML += `<span class="dash-tag"><i class="fa-solid fa-people-group"></i> Demographics</span>`;
  if (state.selectedModules.has('industry'))     tags.innerHTML += `<span class="dash-tag"><i class="fa-solid fa-industry"></i> Industry</span>`;
  if (state.selectedModules.has('businesses'))   tags.innerHTML += `<span class="dash-tag"><i class="fa-solid fa-building"></i> Businesses</span>`;
  if (state.selectedModules.has('leads'))        tags.innerHTML += `<span class="dash-tag"><i class="fa-solid fa-user-tie"></i> Leads</span>`;

  // KYL pin context
  $('kyl-pin-context').textContent = pin;
  $('overlay-pin-val').textContent = pin;
  $('overlay-location-val').textContent = `${titleCase(loc.district)}, ${titleCase(loc.state)}`;

  // Show/hide modules
  const moduleMap = {
    demographics: 'module-demographics',
    industry:     'module-industry',
    businesses:   'module-businesses',
    leads:        'module-leads',
  };

  Object.entries(moduleMap).forEach(([key, id]) => {
    $(id).style.display = state.selectedModules.has(key) ? 'block' : 'none';
  });

  // Loading
  $('dash-loading').style.display = 'flex';
  $('dash-modules').style.display = 'none';

  function updateDashboardLocation(data) {
    document.getElementById("dash-pin-value").textContent = data.pincode;

    document.getElementById("dash-address").textContent =
      data.full_address || "Address not available";

    if (data.lat && data.lng) {
      renderMap(data.lat, data.lng);
    }
  }

  try {
    const promises = [];
    if (state.selectedModules.has('demographics')) promises.push(loadDemographics(pin));
    if (state.selectedModules.has('industry'))     promises.push(loadIndustry(loc.state));
    if (state.selectedModules.has('businesses'))   promises.push(loadBusinesses('industry'));
    if (state.selectedModules.has('leads'))        initLeadsModule();

    await Promise.allSettled(promises);
  } finally {
    $('dash-loading').style.display = 'none';
    $('dash-modules').style.display = 'flex';
  }
}

// ── Header navigation ──────────────────────────────────────────
$('btn-home-dash').addEventListener('click', () => showScreen('screen-landing'));
$('btn-breadcrumb-home').addEventListener('click', () => showScreen('screen-landing'));
$('btn-change-selections').addEventListener('click', () => showScreen('screen-selection'));
$('btn-new-search').addEventListener('click', () => {
  state.pin = '';
  state.locationData = null;
  state.demoData = null;
  state.selectedModules.clear();
  $('pin-input').value = '';
  $('btn-analyze').disabled = true;
  document.querySelectorAll('.insight-card').forEach(c => {
    c.classList.remove('selected');
    c.setAttribute('aria-checked', 'false');
  });
  $('btn-continue').disabled = true;
  showScreen('screen-landing');
});

// ═══════════════════════════════════════════════════════════════
//  MODULE A — DEMOGRAPHICS
// ═══════════════════════════════════════════════════════════════
async function loadDemographics(pin) {
  const loc = state.locationData;
  const demo = state.demoData;

  // Update location label
  $('demo-location-label').textContent = `${titleCase(loc.district)} District, ${titleCase(loc.state)}`;

  // Metrics
  if (demo) {
    $('dm-total-pop').textContent = formatNum(demo.total_pop);
    $('dm-households').textContent = formatNum(demo.households);
    $('dm-literacy').textContent = formatPct(demo.literacy);
    $('dm-work-rate').textContent = formatPct(demo.work_rate);
    const sexRatio = demo.male > 0 ? Math.round((demo.female / demo.male) * 1000) : '—';
    $('dm-sex-ratio').textContent = sexRatio !== '—' ? sexRatio + '/1000' : '—';
  }

  // Fetch chart data
  try {
    const res = await fetch(`${API_BASE}/api/charts/demographics/${pin}`);
    if (!res.ok) throw new Error('Chart data unavailable');
    const d = await res.json();

    renderPieChart('chart-gender', d.gender.labels, d.gender.values, ['#005eac', '#42a5f5']);
    renderDoughnutChart('chart-age', d.age.labels, d.age.values, ['#005eac', '#1976d2', '#42a5f5', '#90caf9']);
    renderBarHChart('chart-social', d.social.labels, d.social.values, '#005eac');
    renderDoughnutChart('chart-literacy', d.literacy.labels, d.literacy.values, ['#005eac', '#e3f2fd']);
    renderDoughnutChart('chart-work', d.work.labels, d.work.values, ['#005eac', '#90caf9']);
    renderPieChart('chart-workers-gender', d.workers_gender.labels, d.workers_gender.values, ['#005eac', '#42a5f5']);

  } catch (e) {
    console.warn('Demographics chart error:', e);
    // Render fallback using demo data
    if (demo) {
      renderPieChart('chart-gender', ['Male', 'Female'], [demo.male, demo.female], ['#005eac', '#42a5f5']);
    }
  }

  // Education funnel
  try {
    const res = await fetch(`${API_BASE}/api/charts/education?state=${encodeURIComponent(loc.state)}`);
    if (!res.ok) throw new Error('Education data unavailable');
    const d = await res.json();
    if (Array.isArray(d) && d.length) {
        const labels = d.map(row => row['Education Level']);
        const values = d.map(row => row['Count']);
        renderFunnelChart('chart-education', labels, values);
     } 
    else {
        throw new Error('Invalid education data');
        }
  } catch (e) {
    console.warn('Education chart error:', e);
    renderEducationFunnelFallback();
  }
}

// ═══════════════════════════════════════════════════════════════
//  MODULE B — INDUSTRY
// ═══════════════════════════════════════════════════════════════
async function loadIndustry(state_name, gender = 'All', tru = 'All', workerType = 'All') {
  try {
    // Industrial charts
    const iRes = await fetch(`${API_BASE}/api/charts/industrial?state=${encodeURIComponent(state_name)}&gender=${gender}&tru=${tru}`);
    if (!iRes.ok) throw new Error('Industrial data unavailable');
    const iData = await iRes.json();

    if (iData.donut) {
      renderDonutHHI(iData.donut);
    }
    if (iData.treemap) {
      renderIndustryBars(iData.treemap);
    }
  } catch (e) {
    console.warn('Industry chart error:', e);
  }

  // Occupation charts
  try {
    const oRes = await fetch(`${API_BASE}/api/charts/occupation?state=${encodeURIComponent(state_name)}&gender=${gender}&worker_type=${workerType}`);
    if (!oRes.ok) throw new Error('Occupation data unavailable');
    const oData = await oRes.json();

    if (oData.distribution) {
      renderOccupationChart(oData.distribution);
    }
    if (oData.worker_type_breakdown) {
      renderWorkerTypeChart(oData.worker_type_breakdown);
    }
  } catch (e) {
    console.warn('Occupation chart error:', e);
  }
}

// Filter listeners for industry
$('btn-apply-industry-filter').addEventListener('click', () => {
  if (!state.locationData) return;
  const gender = $('industry-gender').value;
  const tru    = $('industry-tru').value;
  const wtype  = $('occ-worker-type').value;
  loadIndustry(state.locationData.state, gender, tru, wtype);
});

$('occ-worker-type').addEventListener('change', () => {
  $('btn-apply-industry-filter').click();
});

// ═══════════════════════════════════════════════════════════════
//  MODULE C — BUSINESSES
// ═══════════════════════════════════════════════════════════════
async function loadBusinesses(keyword) {
  if (!state.locationData) return;
  const { lat, lng } = state.locationData;

  $('biz-loading').style.display = 'flex';
  $('biz-list').innerHTML = '';
  $('biz-empty').style.display = 'none';
  $('biz-count').textContent = '…';
  $('biz-avg-dist').textContent = '…';
  $('biz-nearest').textContent = '…';
  $('biz-top-category').textContent = '…';

  try {
    const res = await fetch(
      `${API_BASE}/api/places?lat=${lat}&lng=${lng}&keyword=${encodeURIComponent(keyword)}`
    );
    if (!res.ok) throw new Error('Failed to fetch places');
    const places = await res.json();

    $('biz-loading').style.display = 'none';

    if (!places.length) {
      $('biz-empty').style.display = 'flex';
      resetBizMetrics();
      return;
    }

    // Summary metrics
    $('biz-count').textContent = places.length.toString();
    const dists = places.map(p => p.dist).filter(d => typeof d === 'number');
    const avgDist = dists.length ? (dists.reduce((a,b) => a+b, 0) / dists.length).toFixed(1) : '—';
    $('biz-avg-dist').textContent = avgDist + ' km';
    $('biz-nearest').textContent = (dists[0] || 0).toFixed(1) + ' km';

    // Top category
    const cats = {};
    places.forEach(p => {
      (p.types || []).forEach(t => {
        const clean = t.replace(/_/g, ' ');
        cats[clean] = (cats[clean] || 0) + 1;
      });
    });
    const topCat = Object.entries(cats).sort((a,b) => b[1]-a[1])[0];
    $('biz-top-category').textContent = topCat ? titleCase(topCat[0]) : '—';

    // Render list
    const list = $('biz-list');
    places.slice(0, 50).forEach((p, i) => {
      const cat = p.types && p.types[0] ? titleCase(p.types[0].replace(/_/g, ' ')) : 'Business';
      const rating = (p.rating && p.rating !== 'N/A') ? `<span class="biz-item-rating">★ ${p.rating}</span>` : '';
      const item = document.createElement('div');
      item.className = 'biz-item';
      item.innerHTML = `
        <div class="biz-item-rank">${i + 1}</div>

        <div class="biz-item-main">
            <div class="biz-item-name">${escHtml(p.name)}</div>
            <div class="biz-item-address">
            <i class="fa-solid fa-location-dot"
                style="color:var(--text-muted);font-size:10px;margin-right:4px;"></i>
            ${escHtml(p.address)}
            </div>
        </div>

        <div class="biz-item-meta">
            <button
            class="biz-prospect-btn"
            data-company="${escHtml(p.name)}">
            <i class="fa-solid fa-user-tie"></i>
            Prospect
            </button>

            <span class="biz-item-dist">
            ${typeof p.dist === 'number' ? p.dist.toFixed(1) + ' km' : '—'}
            </span>

            ${rating}
            <span class="biz-item-category">${escHtml(cat)}</span>
        </div>
        `;
      list.appendChild(item);
    });

  } catch (err) {
    $('biz-loading').style.display = 'none';
    $('biz-empty').style.display = 'flex';
    resetBizMetrics();
    console.error('Business fetch error:', err);
  }
}

function resetBizMetrics() {
  ['biz-count','biz-avg-dist','biz-nearest','biz-top-category'].forEach(id => $(id).textContent = '—');
}

// Search button
$('btn-search-biz').addEventListener('click', () => {
  const kw = $('biz-keyword').value.trim();
  if (!kw) return;
  document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
  loadBusinesses(kw);
});

$('biz-keyword').addEventListener('keydown', e => {
  if (e.key === 'Enter') $('btn-search-biz').click();
});

// Chips
document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    $('biz-keyword').value = chip.dataset.kw;
    loadBusinesses(chip.dataset.kw);
  });
});

// ═══════════════════════════════════════════════════════════════
//  MODULE D — LEAD INTELLIGENCE
// ═══════════════════════════════════════════════════════════════
function initLeadsModule() {
  // Already set up listeners — just reset UI
  $('leads-list').innerHTML = '';
  $('leads-empty').style.display = 'none';
  $('leads-loading').style.display = 'none';
}

$('btn-search-leads').addEventListener('click', async () => {
  const company = $('lead-company-input').value.trim();
  if (!company) { showToast('Please enter a company name.'); return; }

  $('leads-loading').style.display = 'flex';
  $('leads-list').innerHTML = '';
  $('leads-empty').style.display = 'none';

  try {
    const res = await fetch(`${API_BASE}/api/leadership`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company_name: company }),
    });

    if (!res.ok) throw new Error('Leadership search failed');
    const profiles = await res.json();

    $('leads-loading').style.display = 'none';

    if (!profiles || !profiles.length) {
      $('leads-empty').style.display = 'flex';
      return;
    }

    renderLeadCards(profiles, company);

  } catch (err) {
    $('leads-loading').style.display = 'none';
    $('leads-empty').style.display = 'flex';
    console.error('Leadership error:', err);
    showToast('Could not fetch leadership data. Please try again.');
  }
});

$('lead-company-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') $('btn-search-leads').click();
});

function renderLeadCards(profiles, company) {
  const list = $('leads-list');
  list.innerHTML = '';

  profiles.forEach(p => {
    const initials = getInitials(p.name || '?');
    const hasLinkedIn = p.linkedin && p.linkedin.startsWith('http');
    const linkedinBtn = hasLinkedIn
      ? `<a href="${escHtml(p.linkedin)}" target="_blank" rel="noopener" class="lead-linkedin-btn"><i class="fa-brands fa-linkedin"></i> LinkedIn</a>`
      : `<span class="lead-linkedin-btn no-link"><i class="fa-brands fa-linkedin"></i> Not Found</span>`;

    const card = document.createElement('div');
    card.className = 'lead-card';
    card.innerHTML = `
      <div class="lead-avatar">${escHtml(initials)}</div>
      <div class="lead-info">
        <div class="lead-name">${escHtml(p.name || '—')}</div>
        <div class="lead-title-co">${escHtml(p.title || '—')} · <strong>${escHtml(company)}</strong></div>
      </div>
      <div class="lead-actions">
        <span class="lead-footprint"><i class="fa-solid fa-globe"></i> Public Profile</span>
        ${linkedinBtn}
        <button class="btn-kyl btn-sm" onclick="openKYLOverlay('${escHtml(p.name)}', '${escHtml(company)}')">
          <i class="fa-solid fa-bolt"></i> KnowYourLead
        </button>
      </div>
    `;
    list.appendChild(card);
  });
}

// ═══════════════════════════════════════════════════════════════
//  SCREEN 4 — KYL OVERLAY
// ═══════════════════════════════════════════════════════════════
function openKYLOverlay(name, company) {
  $('screen-kyl-overlay').style.display = 'flex';
}

$('btn-open-kyl').addEventListener('click', () => openKYLOverlay('', ''));

$('btn-overlay-cancel').addEventListener('click', () => {
  $('screen-kyl-overlay').style.display = 'none';
});

$('btn-overlay-proceed').addEventListener('click', () => {
  const pin = state.pin;
  const loc = state.locationData;
  const context = encodeURIComponent(`Pinbook – PIN ${pin} – ${titleCase(loc ? loc.district : '')} ${titleCase(loc ? loc.state : '')}`);
  window.open(`${KYL_URL}?source=pinbook&context=${context}`, '_blank', 'noopener');
  $('screen-kyl-overlay').style.display = 'none';
});

// Close overlay on backdrop click
$('screen-kyl-overlay').addEventListener('click', e => {
  if (e.target === $('screen-kyl-overlay')) $('screen-kyl-overlay').style.display = 'none';
});

// ═══════════════════════════════════════════════════════════════
//  CHART RENDERERS
// ═══════════════════════════════════════════════════════════════

const CHART_DEFAULTS = {
  plugins: {
    legend: {
      labels: {
        font: { family: 'Inter', size: 12 },
        color: '#4a6080',
        padding: 14,
        boxWidth: 12,
      }
    },
    tooltip: {
      backgroundColor: '#0d1b2e',
      titleFont: { family: 'Inter', size: 13, weight: '600' },
      bodyFont: { family: 'Inter', size: 12 },
      padding: 10,
      cornerRadius: 8,
    }
  }
};
function renderFunnelChart(canvasId, labels, values) {
  destroyChart(canvasId);

  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  // ✅ Ensure labels are always strings (Chart.js categorical axis requirement)
  const safeLabels = labels.map(l => String(l));

  // Sort by value descending for funnel effect
  const sorted = safeLabels.map((label, i) => ({
    label,
    value: values[i]
  })).sort((a, b) => b.value - a.value);

  const sortedLabels = sorted.map(d => d.label);
  const sortedValues = sorted.map(d => d.value);
  const maxValue = Math.max(...sortedValues);

  // Funnel color gradient (light → dark)
  const colors = [
    '#005eac',
    '#0052a3',
    '#00479a',
    '#003d91',
    '#003288'
  ];

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sortedLabels,
      datasets: [{
        label: 'Population',
        data: sortedValues,
        backgroundColor: colors.slice(0, sortedLabels.length),
        borderRadius: 8,
        borderSkipped: false
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          ...CHART_DEFAULTS.plugins.tooltip,
          callbacks: {
            label: ctx => `${formatNum(ctx.parsed.x)} people`
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(0,0,0,.04)' },
          ticks: {
            font: { family: 'Inter', size: 11 },
            color: '#7a90a8',
            callback: v => formatNum(v)
          }
        },
        y: {
          type: 'category',
          grid: { display: false },
          ticks: {
            font: { family: 'Inter', size: 12, weight: '500' },
            color: '#4a6080'
          }
        }
      }
    }
  });
}
// // Funnel Chart Renderer
// function renderFunnelChart(canvasId, labels, values) {
//   destroyChart(canvasId);
//   const ctx = document.getElementById(canvasId);
//   if (!ctx) return;
//   const safeLabels = labels.map(l => String(l));

//   // Sort by value descending for funnel effect
//   const sorted = labels.map((label, i) => ({ label, value: values[i] }))
//     .sort((a, b) => b.value - a.value);
  
//   const sortedLabels = sorted.map(d => d.label);
//   const sortedValues = sorted.map(d => d.value);
//   const maxValue = Math.max(...sortedValues);

//   // Create gradient colors for funnel (blue to darker blue)
//   const colors = [
//     '#005eac',
//     '#0052a3',
//     '#00479a',
//     '#003d91',
//     '#003288',
//   ];

//   // Normalize values to create funnel width effect (0-100)
//   const widths = sortedValues.map(v => Math.max(20, (v / maxValue) * 100));

//   new Chart(ctx, {
//     type: 'bar',
//     data: {
//       labels: sortedLabels,
//       datasets: [{
//         label: 'Population',
//         data: sortedValues,
//         backgroundColor: colors.slice(0, sortedLabels.length),
//         borderRadius: 8,
//         borderSkipped: false,
//       }]
//     },
//     options: {
//       indexAxis: 'y',
//       responsive: true,
//       maintainAspectRatio: true,
//       plugins: {
//         legend: { display: false },
//         tooltip: {
//           ...CHART_DEFAULTS.plugins.tooltip,
//           callbacks: {
//             label: ctx => `${formatNum(ctx.parsed.x)} people`,
//           }
//         },
//         filler: { propagate: true }
//       },
//       scales: {
//         x: {
//           stacked: false,
//           grid: { color: 'rgba(0,0,0,.04)' },
//           ticks: { 
//             font: { family: 'Inter', size: 11 }, 
//             color: '#7a90a8',
//             callback: v => formatNum(v)
//           }
//         },
//         y: {
//           grid: { display: false },
//           ticks: { 
//             font: { family: 'Inter', size: 12, weight: '500' }, 
//             color: '#4a6080'
//           }
//         }
//       }
//     }
//   });
// }
function renderPieChart(canvasId, labels, values, colors) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  new Chart(ctx, {
    type: 'pie',
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: colors, borderWidth: 2, borderColor: '#fff' }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: { ...CHART_DEFAULTS.plugins }
    }
  });
}

function renderDoughnutChart(canvasId, labels, values, colors) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: colors, borderWidth: 2, borderColor: '#fff', hoverOffset: 6 }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: '65%',
      plugins: { ...CHART_DEFAULTS.plugins }
    }
  });
}

function renderBarHChart(canvasId, labels, values, color) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  const max = Math.max(...values);
  const colors = values.map((v, i) => {
    const alpha = 0.45 + 0.55 * (v / (max || 1));
    return `rgba(0,94,172,${alpha.toFixed(2)})`;
  });
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderRadius: 4,
        borderSkipped: false,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: CHART_DEFAULTS.plugins.tooltip,
      },
      scales: {
        x: {
          grid: { color: 'rgba(0,0,0,.04)' },
          ticks: { font: { family: 'Inter', size: 11 }, color: '#7a90a8',
            callback: v => formatNum(v) }
        },
        y: { grid: { display: false }, ticks: { font: { family: 'Inter', size: 12 }, color: '#4a6080' } }
      }
    }
  });
}

function renderHBarChart(canvasId, labels, values, color) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  const max = Math.max(...values);
  const bgColors = values.map(v => {
    const pct = v / (max || 1);
    return `rgba(0,${Math.round(94 + 50*pct)},${Math.round(172 - 40*pct)},${0.5 + 0.5*pct})`;
  });

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: bgColors,
        borderRadius: 4,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: CHART_DEFAULTS.plugins.tooltip,
      },
      scales: {
        x: {
          grid: { color: 'rgba(0,0,0,.04)' },
          ticks: { font: { family: 'Inter', size: 11 }, color: '#7a90a8',
            callback: v => formatNum(v) }
        },
        y: {
          grid: { display: false },
          ticks: { font: { family: 'Inter', size: 12 }, color: '#4a6080' }
        }
      }
    }
  });
}

function renderHBarFallback() {
  // Show placeholder education funnel with sample data
  const labels = ['Graduate & above', 'Diploma', 'HSC', 'Matriculation', 'Illiterate'];
  const values = [2800000, 900000, 3200000, 4500000, 5100000];
  renderFunnelChart('chart-education', labels, values);
}

function renderEducationFunnelFallback() {
  // Fallback for education funnel
  const labels = ['Graduate & above', 'Diploma', 'HSC', 'Matriculation', 'Illiterate'];
  const values = [2800000, 900000, 3200000, 4500000, 5100000];
  renderFunnelChart('chart-education', labels, values);
}

function renderDonutHHI(data) {
  destroyChart('chart-hhi-donut');
  const ctx = document.getElementById('chart-hhi-donut');
  if (!ctx) return;

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.labels,
      datasets: [{
        data: data.values,
        backgroundColor: ['#005eac', '#90caf9'],
        borderWidth: 2,
        borderColor: '#fff',
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: '62%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { ...CHART_DEFAULTS.plugins.legend.labels }
        },
        tooltip: CHART_DEFAULTS.plugins.tooltip,
      }
    }
  });

  // Custom legend with HHI %
  const hhi_pct = data.metrics && data.metrics.hhi_pct !== undefined ? data.metrics.hhi_pct : 0;
  $('hhi-legend').innerHTML = `
    <div class="legend-item"><div class="legend-dot" style="background:#005eac;"></div>Household Industry (HHI): ${hhi_pct}%</div>
    <div class="legend-item"><div class="legend-dot" style="background:#90caf9;"></div>Formal Industry: ${(100 - hhi_pct).toFixed(1)}%</div>
  `;
}

function renderIndustryBars(data) {
  destroyChart('chart-industry-bars');
  const ctx = document.getElementById('chart-industry-bars');
  if (!ctx) return;

  const max = Math.max(...data.values);
  const colors = data.values.map((v, i) => {
    const t = i / (data.labels.length - 1 || 1);
    return `rgba(0,${Math.round(94 + 40 * t)},${Math.round(172 - 20 * t)},${0.7 + 0.3 * (v/max)})`;
  });

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.labels.map(l => l.length > 30 ? l.slice(0,28)+'…' : l),
      datasets: [{
        data: data.values,
        backgroundColor: colors,
        borderRadius: 4,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: CHART_DEFAULTS.plugins.tooltip,
      },
      scales: {
        x: {
          grid: { color: 'rgba(0,0,0,.04)' },
          ticks: { font: { family: 'Inter', size: 11 }, color: '#7a90a8',
            callback: v => formatNum(v) }
        },
        y: {
          grid: { display: false },
          ticks: { font: { family: 'Inter', size: 11 }, color: '#4a6080', maxTicksLimit: 12 }
        }
      }
    }
  });
}

function renderOccupationChart(data) {
  destroyChart('chart-occupation');
  const ctx = document.getElementById('chart-occupation');
  if (!ctx) return;

  const colors = data.y.map((_, i) => {
    const t = i / (data.y.length - 1 || 1);
    return `rgba(0,${Math.round(94 + 50*t)},${Math.round(172 - 30*t)},${0.75})`;
  });

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.y,
      datasets: [{
        label: 'Workers',
        data: data.x,
        backgroundColor: colors,
        borderRadius: 4,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: CHART_DEFAULTS.plugins.tooltip,
      },
      scales: {
        x: {
          grid: { color: 'rgba(0,0,0,.04)' },
          ticks: { font: { family: 'Inter', size: 11 }, color: '#7a90a8',
            callback: v => formatNum(v) }
        },
        y: {
          grid: { display: false },
          ticks: { font: { family: 'Inter', size: 12 }, color: '#4a6080' }
        }
      }
    }
  });
}

function renderWorkerTypeChart(workerCounts) {
  destroyChart('chart-worker-type');
  const ctx = document.getElementById('chart-worker-type');
  if (!ctx) return;

  const labels = ['Employers', 'Employees', 'Self-Employed', 'Family Workers'];
  const values = [
    workerCounts.employer || 0,
    workerCounts.employee || 0,
    workerCounts.single_worker || 0,
    workerCounts.family_worker || 0,
  ];

  const colors = ['#005eac', '#1976d2', '#42a5f5', '#90caf9'];

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderWidth: 2,
        borderColor: '#fff',
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: '62%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { ...CHART_DEFAULTS.plugins.legend.labels }
        },
        tooltip: {
          ...CHART_DEFAULTS.plugins.tooltip,
          callbacks: {
            label: ctx => `${ctx.label}: ${formatNum(ctx.parsed)}`
          }
        },
      }
    }
  });
}
async function prospectCompany(companyName) {
  try {
    console.log('Prospecting:', companyName);

    const res = await fetch(`${API_BASE}/api/leadership`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company_name: companyName })
    });

    if (!res.ok) throw new Error('Leadership fetch failed');

    const leaders = await res.json();
    console.log('Leadership result:', leaders);

    if (!leaders.length) {
      alert(`No leadership data found for ${companyName}`);
      return;
    }

    // TODO: Replace this with modal / side panel later
    alert(
      `Leadership for ${companyName}:\n\n` +
      leaders.map(l => `${l.name} — ${l.title}`).join('\n')
    );

  } catch (err) {
    console.error(err);
    alert('Failed to fetch leadership data');
  }
}
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.biz-prospect-btn');
  if (!btn) return;

  e.stopPropagation();

  const companyName = btn.dataset.company;
  if (!companyName) return;

  const panel = document.getElementById('prospect-result');

  try {
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i>`;

    const res = await fetch(`${API_BASE}/api/leadership`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company_name: companyName })
    });

    if (!res.ok) throw new Error('Leadership fetch failed');

    const leaders = await res.json();

    if (!leaders.length) {
      panel.innerHTML = `<p class="text-xs text-slate-400">
        No leadership data found for ${companyName}
      </p>`;
      panel.classList.remove('hidden');
      return;
    }

    panel.innerHTML = `
      <div class="prospect-header">
        <h4>Leadership — ${companyName}</h4>
        <button id="prospect-close-btn">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>

      ${leaders.map(l => `
        <div class="prospect-leader">
          <div class="prospect-leader-name">${l.name}</div>
          <div class="prospect-leader-title">${l.title}</div>
        </div>
      `).join('')}
    `;
    

    panel.classList.remove('hidden');

  } catch (err) {
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="fa-solid fa-user-tie"></i> Prospect`;
  }
  document.getElementById('prospect-close-btn')
        .addEventListener('click', () => {
            document.getElementById('prospect-result').classList.add('hidden');
    });
});

// ═══════════════════════════════════════════════════════════════
//  UTILS
// ═══════════════════════════════════════════════════════════════
function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;')
    .replace(/'/g,'&#39;');
}

// ═══════════════════════════════════════════════════════════════
//  GLOBAL EXPORTS (inline onclick handlers)
// ═══════════════════════════════════════════════════════════════
window.openKYLOverlay = openKYLOverlay;

// ── Init ──────────────────────────────────────────────────────
showScreen('screen-landing');
