/**
 * Digital ASHA – Parent Panel Controller (parent.js)
 *
 * All vaccination schedule data is fetched from the backend API.
 * Status is ALWAYS backend-computed — frontend never calculates vaccine status.
 * DB-driven vaccination_schedules table is the source of truth.
 */

// ─── State ────────────────────────────────────────────────────────────────────
let currentUser = null;
let allChildren = [];
let currentChildId = null;
let currentTimeline = [];
let currentFilter = 'all';
let currentChildTab = 'vaccines';
let formVillageId = null;
const today = new Date().toISOString().split('T')[0];

// Helper: compute short age display (e.g., "2y 3m") from ISO DOB
function computeAgeDisplay(dob) {
  if (!dob) return '';
  const b = new Date(dob);
  const now = new Date();
  let years = now.getFullYear() - b.getFullYear();
  let months = now.getMonth() - b.getMonth();
  if (now.getDate() < b.getDate()) {
    months -= 1;
  }
  if (months < 0) { years -= 1; months += 12; }
  const parts = [];
  if (years > 0) parts.push(years + 'y');
  if (months > 0) parts.push(months + 'm');
  if (parts.length === 0) return '0m';
  return parts.join(' ');
}

// ─── Bootstrap ────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  const user = Auth.checkSession(['parent']);
  if (!user) return;

  currentUser = user;
  document.getElementById('header-avatar').textContent = (user.full_name || user.username || 'P')[0].toUpperCase();
  document.getElementById('f-dob').max = today;

  setupGenderButtons();
  await Promise.all([
    loadDashboard(),
    loadVillages()
  ]);
  loadNotifications();
});

// ─── Section Navigation ───────────────────────────────────────────────────────
function showSection(name) {
  // Map nav aliases
  const sectionId = `sec-${name}`;
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  const section = document.getElementById(sectionId);
  if (section) {
    section.classList.add('active');
    section.scrollTop = 0;
    window.scrollTo(0, 0);
  }

  const navItem = document.getElementById(`nav-${name}`);
  if (navItem) navItem.classList.add('active');

  // Lazy load section data
  if (name === 'children') loadChildrenSection();
  if (name === 'notifications') loadNotifications();
  if (name === 'profile') loadProfile();
  if (name === 'add-child') setupAddChildForm();
  if (name === 'dashboard') loadDashboard();
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const [meData, children] = await Promise.all([
      API.getMe(),
      API.getChildren()
    ]);

    currentUser = { ...currentUser, ...meData };
    allChildren = children;

    // Welcome message
    document.getElementById('dash-welcome-name').textContent = meData.full_name || meData.username;
    document.getElementById('dash-village-name').textContent = ``;

    document.getElementById('header-avatar').textContent = (meData.full_name || meData.username || 'P')[0].toUpperCase();
    document.getElementById('profile-name').textContent = meData.full_name || meData.username;
    document.getElementById('profile-username').textContent = meData.username;
    document.getElementById('profile-phone').textContent = meData.phone || '';
    document.getElementById('profile-avatar').textContent = (meData.full_name || 'P')[0].toUpperCase();

    // Aggregate KPIs across all children
    let totalCompleted = 0, totalDue = 0, totalOverdue = 0;
    let alertTexts = [];

    // Fetch detailed metrics for each child
    const detailedPromises = children.map(c => API.getChildDetail(c.id).catch(() => null));
    const detailed = await Promise.all(detailedPromises);

    detailed.forEach(child => {
      if (!child) return;
      child.age_display = child.age_formatted || (child.date_of_birth ? computeAgeDisplay(child.date_of_birth) : '');
      const m = child.immunization_metrics;
      if (!m) return;
      totalCompleted += m.completed_vaccines || 0;
      totalDue += m.due_vaccines || 0;
      totalOverdue += m.overdue_vaccines || 0;
      if (m.alert_summary) alertTexts.push(`${child.full_name}: ${m.alert_summary}`);
    });

    document.getElementById('kpi-children').textContent = children.length;
    document.getElementById('kpi-completed').textContent = totalCompleted;
    document.getElementById('kpi-due').textContent = totalDue;
    document.getElementById('kpi-overdue').textContent = totalOverdue;

    // Alert banner
    const alertBanner = document.getElementById('dash-alert-banner');
    if (alertTexts.length > 0) {
      alertBanner.classList.remove('hidden');
      document.getElementById('dash-alert-text').textContent = alertTexts.join(' | ');
    } else {
      alertBanner.classList.add('hidden');
    }

    // Children quick cards
    const list = document.getElementById('dash-children-list');
    if (detailed.length === 0) {
      list.innerHTML = `
        <div class="py-10 text-center">
          <p class="text-4xl mb-2">👶</p>
          <p class="text-sm font-bold text-slate-700">No children registered</p>
          <p class="text-xs text-slate-500 mt-1 mb-4">Add your first child to start tracking vaccinations</p>
          <button onclick="showSection('add-child')" class="px-5 py-2.5 bg-teal-600 text-white text-xs font-bold rounded-xl">+ Register Child</button>
        </div>
      `;
    } else {
      list.innerHTML = detailed.map(ch => ch ? renderQuickChildCard(ch) : '').join('');
    }

  } catch (err) {
    console.error('Dashboard load failed:', err);
    Utils.showToast('Failed to load dashboard data.', 'error');
  }
}

function renderQuickChildCard(child) {
  const m = child.immunization_metrics || {};
  const rate = m.immunization_rate || 0;
  const status = getChildAlertStatus(m);

  return `
    <div onclick="openChildDetail(${child.id})" class="bg-white rounded-2xl border border-slate-200 shadow-sm p-4 cursor-pointer hover:border-teal-300 hover:shadow-md transition-all">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <div class="w-11 h-11 rounded-xl flex items-center justify-center text-2xl ${child.gender === 'Male' ? 'bg-sky-100' : 'bg-pink-100'}">
            ${child.gender === 'Male' ? '👦' : '👧'}
          </div>
          <div>
            <p class="text-sm font-bold text-slate-900">${child.full_name}</p>
            <p class="text-xs text-slate-500 mt-0.5">${child.age_display || ''} • ${child.gender || ''}</p>
          </div>
        </div>
        <div class="text-right">
          ${status}
          <p class="text-[10px] text-slate-500 mt-1">${rate}% done</p>
        </div>
      </div>
      <!-- Mini progress bar -->
      <div class="mt-3 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div class="h-full bg-teal-500 rounded-full transition-all duration-700" style="width:${rate}%"></div>
      </div>
      <div class="mt-2 flex justify-between text-[10px] text-slate-500">
        <span>✅ ${m.completed_vaccines || 0} completed</span>
        ${m.overdue_vaccines > 0 ? `<span class="text-rose-600 font-bold">⚠️ ${m.overdue_vaccines} overdue</span>` : m.due_vaccines > 0 ? `<span class="text-amber-600 font-bold">🔔 ${m.due_vaccines} due</span>` : `<span class="text-emerald-600 font-bold">✓ On track</span>`}
      </div>
    </div>
  `;
}

function getChildAlertStatus(m) {
  if (m.overdue_vaccines > 0) {
    return `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800">Overdue</span>`;
  }
  if (m.due_vaccines > 0) {
    return `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800">Due</span>`;
  }
  return `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">On Track</span>`;
}

// ─── Children Section ─────────────────────────────────────────────────────────
async function loadChildrenSection() {
  const grid = document.getElementById('children-grid');
  grid.innerHTML = `<div class="text-center py-8 text-slate-400 text-xs">Loading...</div>`;

  try {
    const children = await API.getChildren();
    allChildren = children;
    document.getElementById('children-count-label').textContent = `${children.length} child${children.length !== 1 ? 'ren' : ''} registered`;

    if (children.length === 0) {
      grid.innerHTML = `
        <div class="py-12 text-center">
          <p class="text-5xl mb-3">👶</p>
          <p class="text-sm font-bold text-slate-700">No children registered yet</p>
          <p class="text-xs text-slate-500 mt-1 mb-5">Register your child to track vaccinations & health records</p>
          <button onclick="showSection('add-child')" class="px-5 py-3 bg-teal-600 text-white text-sm font-bold rounded-xl shadow-md">+ Register Child</button>
        </div>
      `;
      return;
    }

    const detailPromises = children.map(c => API.getChildDetail(c.id).catch(() => c));
    const detailed = await Promise.all(detailPromises);

    // Ensure each child has a short age display for UI
    detailed.forEach(ch => { if (ch) ch.age_display = ch.age_formatted || (ch.date_of_birth ? computeAgeDisplay(ch.date_of_birth) : ''); });

    grid.innerHTML = detailed.map(child => renderFullChildCard(child)).join('');
  } catch (err) {
    grid.innerHTML = `<div class="text-center py-8 text-rose-500 text-xs">Failed to load children. Please retry.</div>`;
    Utils.showToast('Failed to load children.', 'error');
  }
}

function renderFullChildCard(child) {
  const m = child.immunization_metrics || {};
  const rate = m.immunization_rate || 0;
  const vStatus = child.verification_status || 'pending';
  const vBadge = {
    'verified': '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">✓ Verified</span>',
    'pending': '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800">⏳ Pending</span>',
    'rejected': '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800">✗ Rejected</span>'
  }[vStatus] || '';

  return `
    <div class="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden hover:border-teal-300 hover:shadow-md transition-all">
      
      <!-- Card Header -->
      <div onclick="openChildDetail(${child.id})" class="p-4 cursor-pointer">
        <div class="flex items-start justify-between mb-3">
          <div class="flex items-center space-x-3">
            <div class="w-12 h-12 rounded-2xl flex items-center justify-center text-2xl ${child.gender === 'Male' ? 'bg-sky-100' : 'bg-pink-100'}">
              ${child.gender === 'Male' ? '👦' : '👧'}
            </div>
            <div>
              <h3 class="text-sm font-black text-slate-900">${child.full_name}</h3>
              <p class="text-xs text-slate-500 mt-0.5">${child.age_display || ''}</p>
              ${vBadge}
            </div>
          </div>
          <div class="text-right">
            <p class="text-2xl font-black text-teal-700">${rate}%</p>
            <p class="text-[10px] text-slate-500">immunized</p>
          </div>
        </div>

        <!-- Progress bar -->
        <div class="h-2 bg-slate-100 rounded-full overflow-hidden mb-3">
          <div class="h-full rounded-full transition-all duration-700 ${rate === 100 ? 'bg-emerald-500' : rate >= 70 ? 'bg-teal-500' : 'bg-amber-500'}" style="width:${rate}%"></div>
        </div>

        <!-- Stats row -->
        <div class="grid grid-cols-4 gap-2 text-center">
          <div class="p-1.5 rounded-lg bg-slate-50">
            <p class="text-xs font-black text-slate-900">${m.total_vaccines || 0}</p>
            <p class="text-[9px] text-slate-500">Total</p>
          </div>
          <div class="p-1.5 rounded-lg bg-emerald-50">
            <p class="text-xs font-black text-emerald-700">${m.completed_vaccines || 0}</p>
            <p class="text-[9px] text-emerald-600">Done</p>
          </div>
          <div class="p-1.5 rounded-lg bg-amber-50">
            <p class="text-xs font-black text-amber-700">${m.due_vaccines || 0}</p>
            <p class="text-[9px] text-amber-600">Due</p>
          </div>
          <div class="p-1.5 rounded-lg bg-rose-50">
            <p class="text-xs font-black text-rose-700">${m.overdue_vaccines || 0}</p>
            <p class="text-[9px] text-rose-600">Overdue</p>
          </div>
        </div>
      </div>

      <!-- Card Footer Actions -->
      <div class="border-t border-slate-100 px-4 py-2.5 flex space-x-3">
        <button onclick="openChildDetail(${child.id})" class="flex-1 py-2 text-xs font-bold text-teal-700 hover:bg-teal-50 rounded-xl transition-all">
          💉 View Vaccines
        </button>
        <button onclick="openEditChildModal(${child.id})" class="flex-1 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50 rounded-xl transition-all">
          ✏️ Edit
        </button>
      </div>
    </div>
  `;
}

function filterChildCards() {
  const q = document.getElementById('children-search').value.toLowerCase();
  document.querySelectorAll('#children-grid > div').forEach(card => {
    const name = card.querySelector('h3')?.textContent?.toLowerCase() || '';
    card.style.display = name.includes(q) ? 'block' : 'none';
  });
}

// ─── Child Detail & Vaccination Timeline ──────────────────────────────────────
async function openChildDetail(childId) {
  currentChildId = childId;
  currentFilter = 'all';
  currentChildTab = 'vaccines';
  showSection('child-detail');
  switchChildTab('vaccines');

  try {
    await loadChildDetail(childId);
    await loadVaccinationTimeline(childId);
  } catch (err) {
    Utils.showToast('Failed to load child details.', 'error');
  }
}

async function loadChildDetail(childId) {
  const child = await API.getChildDetail(childId);
  // Ensure age_display is available for templates
  child.age_display = child.age_formatted || (child.date_of_birth ? computeAgeDisplay(child.date_of_birth) : '');
  const m = child.immunization_metrics || {};

  document.getElementById('detail-name').textContent = child.full_name;
  document.getElementById('detail-age').textContent = `${child.age_display || ''} • ${child.gender || ''}`;
  document.getElementById('detail-rch').textContent = child.rch_mcp_number ? `MCP: ${child.rch_mcp_number}` : '';

  const vStatus = child.verification_status || 'pending';
  const badge = document.getElementById('detail-verification-badge');
  badge.textContent = { verified: '✓ Verified by ASHA', pending: '⏳ Pending Verification', rejected: '✗ Review Required' }[vStatus] || 'Pending';

  document.getElementById('dm-total').textContent = m.total_vaccines || 0;
  document.getElementById('dm-done').textContent = m.completed_vaccines || 0;
  document.getElementById('dm-due').textContent = m.due_vaccines || 0;
  document.getElementById('dm-overdue').textContent = m.overdue_vaccines || 0;
  document.getElementById('dm-rate').textContent = `${m.immunization_rate || 0}%`;
  document.getElementById('dm-progress-bar').style.width = `${m.immunization_rate || 0}%`;

  // Child Info Tab
  buildChildInfoTab(child);

  // Growth Tab
  buildGrowthTab(child.growth_records || []);
}

function buildChildInfoTab(child) {
  const fields = [
    { label: 'Full Name', value: child.full_name },
    { label: 'Date of Birth', value: child.date_of_birth ? new Date(child.date_of_birth).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : 'N/A' },
    { label: 'Age', value: child.age_display || 'N/A' },
    { label: 'Gender', value: child.gender || 'N/A' },
    { label: 'Mother\'s Name', value: child.mother_name || 'Not provided' },
    { label: 'Father\'s Name', value: child.father_name || 'Not provided' },
    { label: 'Village', value: child.village_name || 'N/A' },
    { label: 'House Number', value: child.house_number || 'N/A' },
    { label: 'Contact Number', value: child.parent_contact || 'N/A' },
    { label: 'Birth Weight', value: child.birth_weight_kg ? `${child.birth_weight_kg} kg` : 'Not recorded' },
    { label: 'Birth Place', value: child.birth_place || 'N/A' },
    { label: 'MCP/RCH Number', value: child.rch_mcp_number || 'To be assigned' },
    { label: 'Verification Status', value: child.verification_status || 'Pending' },
    { label: 'Registered On', value: child.registration_date ? new Date(child.registration_date).toLocaleDateString('en-IN') : 'N/A' },
  ];

  document.getElementById('child-info-fields').innerHTML = fields.map(f => `
    <div class="flex items-start justify-between py-2.5 border-b border-slate-100 last:border-0">
      <span class="text-xs text-slate-500 font-medium flex-shrink-0 w-36">${f.label}</span>
      <span class="text-xs font-semibold text-slate-900 text-right">${f.value}</span>
    </div>
  `).join('');

  document.getElementById('edit-info-btn').onclick = () => openEditChildModal(child.id);
}

function buildGrowthTab(records) {
  const container = document.getElementById('growth-records-list');
  if (!records.length) {
    container.innerHTML = `<div class="py-8 text-center"><p class="text-3xl mb-2">📊</p><p class="text-xs text-slate-500">No growth records yet. Your ASHA worker will record growth measurements during home visits.</p></div>`;
    return;
  }

  container.innerHTML = records.map(r => {
    const statusColors = {
      'Normal': 'bg-emerald-100 text-emerald-800',
      'Moderate': 'bg-amber-100 text-amber-800',
      'Severe': 'bg-rose-100 text-rose-800',
      'Wasted': 'bg-orange-100 text-orange-800',
    };
    const statusColor = statusColors[r.nutritional_status] || 'bg-slate-100 text-slate-600';
    return `
      <div class="bg-white rounded-2xl border border-slate-200 p-4">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs font-bold text-slate-900">${new Date(r.recorded_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</p>
          ${r.nutritional_status ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${statusColor}">${r.nutritional_status}</span>` : ''}
        </div>
        <div class="grid grid-cols-3 gap-2 text-center text-xs">
          ${r.weight_kg ? `<div class="p-2 bg-slate-50 rounded-xl"><p class="font-black text-slate-900">${r.weight_kg} kg</p><p class="text-slate-500">Weight</p></div>` : ''}
          ${r.height_cm ? `<div class="p-2 bg-slate-50 rounded-xl"><p class="font-black text-slate-900">${r.height_cm} cm</p><p class="text-slate-500">Height</p></div>` : ''}
          ${r.muac_cm ? `<div class="p-2 bg-slate-50 rounded-xl"><p class="font-black text-slate-900">${r.muac_cm} cm</p><p class="text-slate-500">MUAC</p></div>` : ''}
        </div>
        ${r.notes ? `<p class="text-xs text-slate-500 mt-2">Note: ${r.notes}</p>` : ''}
      </div>
    `;
  }).join('');
}

// ─── Vaccination Timeline (DB-Driven) ─────────────────────────────────────────
async function loadVaccinationTimeline(childId, statusFilter = 'all') {
  const container = document.getElementById('vaccine-timeline');
  container.innerHTML = `<div class="text-center py-8 text-slate-400 text-xs">⏳ Loading schedule from National UIP database...</div>`;

  try {
    // Backend returns schedule from vaccination_schedules DB table — not hardcoded
    const filterParam = statusFilter !== 'all' ? `?status_filter=${statusFilter}` : '';
    const data = await API.request(`/immunizations/timeline/${childId}${filterParam}`);
    currentTimeline = data.timeline || [];
    renderTimeline(currentTimeline, data.metrics);
  } catch (err) {
    container.innerHTML = `<div class="text-center py-8 text-rose-500 text-xs">Failed to load vaccination schedule. Please retry.</div>`;
    console.error('Timeline load failed:', err);
  }
}

function renderTimeline(timeline, metrics) {
  const container = document.getElementById('vaccine-timeline');

  if (!timeline.length) {
    container.innerHTML = `
      <div class="py-10 text-center">
        <p class="text-4xl mb-2">✅</p>
        <p class="text-sm font-bold text-slate-700">No vaccinations found</p>
        <p class="text-xs text-slate-500 mt-1">Try a different filter</p>
      </div>
    `;
    return;
  }

  // Group by category (from DB vaccination_schedules.category field)
  const grouped = {};
  timeline.forEach(entry => {
    const cat = entry.category || 'Other';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(entry);
  });

  // Category display order (matches UIP schedule)
  const catOrder = ['Birth', '6 Weeks', '10 Weeks', '14 Weeks', '9-12 Months', '16-24 Months', '5-6 Years', '10 Years', '16 Years'];
  const sortedCats = [
    ...catOrder.filter(c => grouped[c]),
    ...Object.keys(grouped).filter(c => !catOrder.includes(c))
  ];

  container.innerHTML = sortedCats.map(category => {
    const vaccines = grouped[category];
    const catStatus = getCategoryStatus(vaccines);

    return `
      <div class="mb-5">
        <!-- Category Header -->
        <div class="flex items-center space-x-3 mb-3">
          <div class="flex-shrink-0 w-2 h-2 rounded-full ${catStatus.dot}"></div>
          <h4 class="text-xs font-black text-slate-700 uppercase tracking-wider">${category}</h4>
          <div class="flex-1 h-px bg-slate-200"></div>
          <span class="text-[10px] font-bold ${catStatus.text} px-2 py-0.5 rounded-full ${catStatus.bg}">${catStatus.label}</span>
        </div>

        <!-- Vaccine Cards -->
        <div class="space-y-2">
          ${vaccines.map(v => renderVaccineCard(v)).join('')}
        </div>
      </div>
    `;
  }).join('');
}

function getCategoryStatus(vaccines) {
  const hasOverdue = vaccines.some(v => v.status === 'overdue');
  const hasDue = vaccines.some(v => v.status === 'due');
  const allDone = vaccines.every(v => v.status === 'administered');

  if (allDone) return { dot: 'bg-emerald-500', text: 'text-emerald-700', bg: 'bg-emerald-100', label: '✓ Complete' };
  if (hasOverdue) return { dot: 'bg-rose-500', text: 'text-rose-700', bg: 'bg-rose-100', label: '⚠ Overdue' };
  if (hasDue) return { dot: 'bg-amber-500', text: 'text-amber-700', bg: 'bg-amber-100', label: '🔔 Due Now' };
  return { dot: 'bg-sky-400', text: 'text-sky-700', bg: 'bg-sky-100', label: '⏳ Upcoming' };
}

function renderVaccineCard(vaccine) {
  const statusConfig = {
    administered: {
      border: 'border-l-emerald-400',
      bg: 'bg-emerald-50',
      badge: 'bg-emerald-100 text-emerald-800',
      icon: '✅',
      label: 'Completed'
    },
    due: {
      border: 'border-l-amber-400',
      bg: 'bg-amber-50',
      badge: 'bg-amber-100 text-amber-800',
      icon: '🔔',
      label: 'Due Now'
    },
    overdue: {
      border: 'border-l-rose-500',
      bg: 'bg-rose-50',
      badge: 'bg-rose-100 text-rose-800',
      icon: '⚠️',
      label: `Overdue ${vaccine.days_overdue > 0 ? `(${vaccine.days_overdue}d)` : ''}`
    },
    upcoming: {
      border: 'border-l-sky-400',
      bg: 'bg-white',
      badge: 'bg-sky-100 text-sky-800',
      icon: '⏳',
      label: 'Upcoming'
    },
    not_applicable: {
      border: 'border-l-slate-300',
      bg: 'bg-slate-50',
      badge: 'bg-slate-100 text-slate-500',
      icon: '–',
      label: 'N/A'
    }
  };

  const cfg = statusConfig[vaccine.status] || statusConfig.upcoming;
  const scheduledDate = new Date(vaccine.scheduled_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });

  return `
    <div onclick="openVaccineModal(${vaccine.record_id})" 
         class="border-l-4 ${cfg.border} ${cfg.bg} rounded-r-2xl p-3.5 cursor-pointer hover:shadow-sm transition-all">
      <div class="flex items-start justify-between">
        <div class="flex-1 pr-2">
          <div class="flex items-center space-x-2 mb-0.5">
            <span class="text-sm">${cfg.icon}</span>
            <p class="text-xs font-black text-slate-900">${vaccine.vaccine_name}</p>
          </div>
          ${vaccine.dose_number > 1 ? `<p class="text-[10px] text-slate-500 ml-6">Dose ${vaccine.dose_number}</p>` : ''}
          <p class="text-[10px] text-slate-500 ml-6 mt-0.5">
            Scheduled: <strong>${scheduledDate}</strong>
            ${vaccine.days_overdue > 0 ? ` • <span class="text-rose-600">${vaccine.days_overdue}d overdue</span>` : ''}
          </p>
          ${vaccine.administered_date ? `
            <p class="text-[10px] text-emerald-600 font-semibold ml-6 mt-0.5">
              Given: ${new Date(vaccine.administered_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
              ${vaccine.administered_by_name ? ` by ${vaccine.administered_by_name}` : ''}
            </p>
          ` : ''}
        </div>
        <div class="flex flex-col items-end space-y-1">
          <span class="px-2 py-0.5 rounded-full text-[9px] font-bold ${cfg.badge}">${cfg.label}</span>
          <span class="text-[10px] text-slate-400">ⓘ Details</span>
        </div>
      </div>
    </div>
  `;
}

function switchChildTab(tab) {
  currentChildTab = tab;
  ['vaccines', 'growth', 'info'].forEach(t => {
    const tabEl = document.getElementById(`tab-${t}`);
    const btnEl = document.getElementById(`tab-${t}-btn`);
    if (tabEl) tabEl.classList.toggle('hidden', t !== tab);
    if (btnEl) {
      btnEl.classList.toggle('text-teal-700', t === tab);
      btnEl.classList.toggle('border-teal-600', t === tab);
      btnEl.classList.toggle('text-slate-500', t !== tab);
      btnEl.classList.toggle('border-transparent', t !== tab);
    }
  });
}

function filterTimeline(filter) {
  currentFilter = filter;
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.classList.remove('bg-teal-600', 'text-white');
    btn.classList.add('bg-white', 'text-slate-600', 'border', 'border-slate-300');
  });
  const activeBtn = document.getElementById(`filter-${filter}`);
  if (activeBtn) {
    activeBtn.classList.add('bg-teal-600', 'text-white');
    activeBtn.classList.remove('bg-white', 'text-slate-600', 'border', 'border-slate-300');
  }
  if (currentChildId) {
    loadVaccinationTimeline(currentChildId, filter);
  }
}

// ─── Vaccine Detail Modal ─────────────────────────────────────────────────────
function openVaccineModal(recordId) {
  const vaccine = currentTimeline.find(v => v.record_id === recordId);
  if (!vaccine) return;

  document.getElementById('vmodal-name').textContent = vaccine.vaccine_name;

  const scheduledDate = new Date(vaccine.scheduled_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });

  const cfg = {
    administered: { color: 'text-emerald-700', bg: 'bg-emerald-50 border-emerald-200', icon: '✅' },
    due: { color: 'text-amber-700', bg: 'bg-amber-50 border-amber-200', icon: '🔔' },
    overdue: { color: 'text-rose-700', bg: 'bg-rose-50 border-rose-200', icon: '⚠️' },
    upcoming: { color: 'text-sky-700', bg: 'bg-sky-50 border-sky-200', icon: '⏳' },
  }[vaccine.status] || { color: 'text-slate-600', bg: 'bg-slate-50 border-slate-200', icon: '–' };

  document.getElementById('vmodal-content').innerHTML = `
    <!-- Status Banner -->
    <div class="p-3.5 rounded-2xl ${cfg.bg} border flex items-center space-x-3">
      <span class="text-2xl">${cfg.icon}</span>
      <div>
        <p class="text-sm font-black ${cfg.color}">${vaccine.status_label}</p>
        ${vaccine.days_overdue > 0 ? `<p class="text-xs ${cfg.color}">Please visit your nearest health center immediately</p>` : ''}
      </div>
    </div>

    <!-- Vaccine Details -->
    <div class="bg-white rounded-2xl border border-slate-200 p-4 space-y-3">
      <h4 class="text-xs font-bold text-slate-500 uppercase tracking-wider">Vaccine Information</h4>
      ${infoRow('Vaccine Name', vaccine.vaccine_name)}
      ${infoRow('Vaccine Code', vaccine.vaccine_code || 'N/A')}
      ${infoRow('Dose Number', `Dose ${vaccine.dose_number}`)}
      ${infoRow('Category', vaccine.category)}
      ${infoRow('Recommended Timing', vaccine.recommended_timing)}
      ${infoRow('Dose Amount', vaccine.dose_amount || 'N/A')}
      ${infoRow('Route', vaccine.route || 'N/A')}
      ${infoRow('Site', vaccine.site || 'N/A')}
      ${vaccine.prevents_diseases ? infoRow('Prevents', vaccine.prevents_diseases) : ''}
    </div>

    <!-- Schedule -->
    <div class="bg-white rounded-2xl border border-slate-200 p-4 space-y-3">
      <h4 class="text-xs font-bold text-slate-500 uppercase tracking-wider">Schedule</h4>
      ${infoRow('Scheduled Date', scheduledDate)}
      ${vaccine.administered_date ? infoRow('Administered On', new Date(vaccine.administered_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })) : ''}
      ${vaccine.administered_by_name ? infoRow('Given By', vaccine.administered_by_name) : ''}
      ${vaccine.batch_number ? infoRow('Batch Number', vaccine.batch_number) : ''}
      ${vaccine.session_site ? infoRow('Session Site', vaccine.session_site) : ''}
      ${vaccine.aefi_reported ? `<div class="p-2.5 rounded-xl bg-orange-50 border border-orange-200 text-xs text-orange-700">⚠️ Side effect reported: ${vaccine.aefi_details || 'Contact your ASHA worker for details.'}</div>` : ''}
    </div>

    <!-- Info note -->
    <div class="p-3 rounded-2xl bg-slate-50 border border-slate-200 text-[10px] text-slate-500 flex items-start space-x-2">
      <span>🗄️</span>
      <span>Schedule data from <strong>National UIP database</strong>. Status computed by backend system, not by this app.</span>
    </div>
  `;

  document.getElementById('vaccine-modal').classList.remove('hidden');
}

function closeVaccineModal() {
  document.getElementById('vaccine-modal').classList.add('hidden');
}

function infoRow(label, value) {
  return `
    <div class="flex items-start justify-between">
      <span class="text-[10px] text-slate-500 font-medium flex-shrink-0 w-28">${label}</span>
      <span class="text-xs font-semibold text-slate-900 text-right">${value}</span>
    </div>
  `;
}

// ─── Add Child (Multi-step Form) ──────────────────────────────────────────────
let formCurrentStep = 1;

function setupAddChildForm() {
  formCurrentStep = 1;
  goToStep1();
  document.getElementById('add-child-form').reset();
  document.querySelectorAll('.gender-label').forEach(l => l.classList.remove('!border-teal-500', 'bg-teal-50'));
  document.getElementById('child-age-preview').classList.add('hidden');

  // Pre-fill parent name
  if (currentUser) {
    document.getElementById('f-parent-name').value = currentUser.full_name || '';
    document.getElementById('f-phone').value = currentUser.phone || '';
  }
}

async function loadVillages() {
  try {
    const state = document.getElementById('f-state');
    const district = document.getElementById('f-district');
    const taluka = document.getElementById('f-taluka');
    const village = document.getElementById('f-village');
    const fill = (el, placeholder, rows) => {
      el.innerHTML = `<option value="">${placeholder}</option>` +
        rows.map(row => `<option value="${row.id}">${Utils.escapeHtml(row.name)}</option>`).join('');
      el.disabled = rows.length === 0;
    };
    fill(state, '-- Choose state / UT --', await API.getLocationStates());
    state.addEventListener('change', async () => {
      fill(district, '-- Choose district --', state.value ? await API.getLocationDistricts(state.value) : []);
      fill(taluka, '-- Choose taluka / sub-district --', []);
      fill(village, '-- Choose village --', []);
    });
    district.addEventListener('change', async () => {
      fill(taluka, '-- Choose taluka / sub-district --', district.value ? await API.getLocationTalukas(district.value) : []);
      fill(village, '-- Choose village --', []);
    });
    taluka.addEventListener('change', async () => {
      fill(village, '-- Choose village --', taluka.value ? await API.getLocationVillages(taluka.value) : []);
    });
  } catch (err) {
    console.error('Failed to load villages:', err);
  }
}

function setupGenderButtons() {
  document.querySelectorAll('.gender-opt').forEach(opt => {
    opt.addEventListener('click', () => {
      document.querySelectorAll('.gender-label').forEach(l => l.classList.remove('!border-teal-500', 'bg-teal-50'));
      opt.querySelector('.gender-label').classList.add('!border-teal-500', 'bg-teal-50');
    });
  });

  document.getElementById('f-dob').addEventListener('change', function() {
    const dob = new Date(this.value);
    const today = new Date();
    if (dob > today) {
      document.getElementById('err-dob').textContent = 'Date of birth cannot be in the future.';
      document.getElementById('err-dob').classList.remove('hidden');
      document.getElementById('child-age-preview').classList.add('hidden');
      return;
    }
    document.getElementById('err-dob').classList.add('hidden');

    const days = Math.floor((today - dob) / (1000 * 60 * 60 * 24));
    let age;
    if (days < 30) age = `${days} day${days !== 1 ? 's' : ''} old`;
    else if (days < 365) age = `${Math.floor(days / 30)} month${Math.floor(days / 30) !== 1 ? 's' : ''} old`;
    else {
      const years = Math.floor(days / 365);
      const months = Math.floor((days % 365) / 30);
      age = `${years} year${years !== 1 ? 's' : ''} ${months > 0 ? months + ' month' + (months !== 1 ? 's' : '') : ''} old`;
    }

    const preview = document.getElementById('child-age-preview');
    preview.textContent = `Child will be ${age.trim()} • UIP schedule will be auto-generated from National UIP database`;
    preview.classList.remove('hidden');
  });
}

function goToStep1() {
  formCurrentStep = 1;
  document.getElementById('form-step-1').classList.add('active');
  document.getElementById('form-step-2').classList.remove('active');
  document.getElementById('si-1').className = 'step-indicator w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold active';
  document.getElementById('si-2').className = 'step-indicator w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold pending';
  document.getElementById('step-line-fill').style.width = '0%';
}

function goToStep2() {
  // Validate step 1
  if (!document.getElementById('f-parent-name').value.trim()) {
    Utils.showToast('Please enter your name.', 'error');
    document.getElementById('f-parent-name').focus();
    return;
  }
  const phone = document.getElementById('f-phone').value.trim();
  if (!phone || !/^\d{10}$/.test(phone)) {
    Utils.showToast('Please enter a valid 10-digit mobile number.', 'error');
    document.getElementById('f-phone').focus();
    return;
  }
  if (!document.getElementById('f-village').value) {
    Utils.showToast('Please select your village.', 'error');
    return;
  }

  formCurrentStep = 2;
  document.getElementById('form-step-1').classList.remove('active');
  document.getElementById('form-step-2').classList.add('active');
  document.getElementById('si-1').className = 'step-indicator w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold done';
  document.getElementById('si-2').className = 'step-indicator w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold active';
  document.getElementById('step-line-fill').style.width = '100%';
}

async function submitChildForm() {
  const childName = document.getElementById('f-child-name').value.trim();
  const dob = document.getElementById('f-dob').value;
  const genderInput = document.querySelector('input[name="gender"]:checked');
  const gender = genderInput ? genderInput.value : null;

  let valid = true;

  if (!childName) {
    document.getElementById('err-child-name').textContent = 'Child name is required.';
    document.getElementById('err-child-name').classList.remove('hidden');
    valid = false;
  } else {
    document.getElementById('err-child-name').classList.add('hidden');
  }

  if (!dob) {
    document.getElementById('err-dob').textContent = 'Date of birth is required.';
    document.getElementById('err-dob').classList.remove('hidden');
    valid = false;
  } else if (new Date(dob) > new Date()) {
    document.getElementById('err-dob').textContent = 'Date of birth cannot be in the future.';
    document.getElementById('err-dob').classList.remove('hidden');
    valid = false;
  } else {
    document.getElementById('err-dob').classList.add('hidden');
  }

  if (!gender) {
    document.getElementById('err-gender').textContent = 'Please select a gender.';
    document.getElementById('err-gender').classList.remove('hidden');
    valid = false;
  } else {
    document.getElementById('err-gender').classList.add('hidden');
  }

  if (!valid) return;

  const submitBtn = document.querySelector('#form-step-2 button[type="button"]:last-child');
  submitBtn.textContent = 'Registering... ⏳';
  submitBtn.disabled = true;

  try {
    const payload = {
      full_name: childName,
      date_of_birth: dob,
      gender: gender,
      location_state_id: parseInt(document.getElementById('f-state').value),
      location_district_id: parseInt(document.getElementById('f-district').value),
      location_taluka_id: parseInt(document.getElementById('f-taluka').value),
      location_village_id: parseInt(document.getElementById('f-village').value),
      house_number: document.getElementById('f-house').value.trim() || null,
      parent_contact: document.getElementById('f-phone').value.trim(),
      mother_name: document.getElementById('f-mother').value.trim() || null,
      father_name: document.getElementById('f-father').value.trim() || null,
      birth_weight_kg: document.getElementById('f-weight').value ? parseFloat(document.getElementById('f-weight').value) : null,
      birth_place: document.getElementById('f-birthplace').value || null,
    };

    await API.registerChild(payload);
    Utils.showToast(`✅ ${childName} registered! UIP vaccination schedule generated from database.`, 'success');

    // Refresh data and go to children section
    await loadDashboard();
    showSection('children');
    document.getElementById('add-child-form').reset();
    document.querySelectorAll('.gender-label').forEach(l => l.classList.remove('!border-teal-500', 'bg-teal-50'));

  } catch (err) {
    Utils.showToast(err.message || 'Failed to register child.', 'error');
  } finally {
    submitBtn.textContent = 'Register Child ✓';
    submitBtn.disabled = false;
  }
}

function cancelAddChild() {
  showSection('children');
}

// ─── Edit Child Modal ─────────────────────────────────────────────────────────
let editingChildId = null;

async function openEditChildModal(childId) {
  editingChildId = childId || currentChildId;
  if (!editingChildId) return;

  try {
    const child = await API.getChildDetail(editingChildId);
    document.getElementById('edit-name').value = child.full_name || '';
    document.getElementById('edit-dob').value = child.date_of_birth || '';
    document.getElementById('edit-mother').value = child.mother_name || '';
    document.getElementById('edit-father').value = child.father_name || '';
    document.getElementById('edit-contact').value = child.parent_contact || '';
    document.getElementById('edit-house').value = child.house_number || '';
    document.getElementById('edit-child-modal').classList.remove('hidden');
  } catch (err) {
    Utils.showToast('Failed to load child details.', 'error');
  }
}

function closeEditModal() {
  document.getElementById('edit-child-modal').classList.add('hidden');
  editingChildId = null;
}

async function submitEditChild() {
  if (!editingChildId) return;

  const newDob = document.getElementById('edit-dob').value;
  const payload = {
    full_name: document.getElementById('edit-name').value.trim(),
    date_of_birth: newDob,
    mother_name: document.getElementById('edit-mother').value.trim() || null,
    father_name: document.getElementById('edit-father').value.trim() || null,
    parent_contact: document.getElementById('edit-contact').value.trim() || null,
    house_number: document.getElementById('edit-house').value.trim() || null,
  };

  if (!payload.full_name) {
    Utils.showToast('Child name is required.', 'error');
    return;
  }

  try {
    await API.updateChild(editingChildId, payload);
    closeEditModal();
    Utils.showToast('Child information updated. Vaccination schedule recalculated.', 'success');

    // Refresh current view
    if (currentChildId === editingChildId) {
      await loadChildDetail(editingChildId);
      await loadVaccinationTimeline(editingChildId, currentFilter);
    }
    loadDashboard();
  } catch (err) {
    Utils.showToast(err.message || 'Failed to update child.', 'error');
  }
}

// ─── Notifications Center ───────────────────────────────────────────────────
let currentParentNotifFilter = 'all';

function filterParentNotifications(filter) {
  currentParentNotifFilter = filter;
  ['all', 'unread', 'high'].forEach(f => {
    const btn = document.getElementById(`notif-pill-${f}`);
    if (btn) {
      if (f === filter.toLowerCase()) {
        btn.className = 'px-3 py-1.5 rounded-full font-bold bg-teal-600 text-white shadow-sm';
      } else {
        btn.className = 'px-3 py-1.5 rounded-full font-bold bg-slate-100 text-slate-700 hover:bg-slate-200';
      }
    }
  });
  loadNotifications();
}

async function loadNotifications() {
  const list = document.getElementById('notifications-list');
  if (list) list.innerHTML = `<div class="text-center py-8 text-slate-400 text-xs">Loading notifications...</div>`;

  try {
    const params = {};
    if (currentParentNotifFilter === 'unread') params.is_read = false;
    if (currentParentNotifFilter === 'HIGH') params.priority = 'HIGH';

    const notifs = await API.getNotifications(params);
    const unreadRes = await API.getUnreadNotificationCount();
    const unreadCount = unreadRes.unread_count || 0;

    const badge = document.getElementById('notif-badge');
    if (badge) {
      if (unreadCount > 0) {
        badge.textContent = unreadCount > 9 ? '9+' : unreadCount;
        badge.classList.remove('hidden');
      } else {
        badge.classList.add('hidden');
      }
    }

    const unreadPillBadge = document.getElementById('parent-unread-badge');
    if (unreadPillBadge) unreadPillBadge.textContent = unreadCount;

    if (!list) return;

    if (!notifs.length) {
      list.innerHTML = `
        <div class="py-10 text-center">
          <p class="text-4xl mb-2">🔔</p>
          <p class="text-sm font-bold text-slate-700">No notifications found</p>
          <p class="text-xs text-slate-500 mt-1">You're all caught up with your child's immunization schedule.</p>
        </div>
      `;
      return;
    }

    list.innerHTML = notifs.map(n => {
      const icon = {
        vaccine_upcoming: '⏳',
        vaccine_due: '🔔',
        vaccine_overdue: '⚠️',
        vaccine_administered: '✅',
        verification_required: '📋',
        verification_completed: '✓',
        asha_followup: '🏡',
        parent_updated_info: '✏️',
        general: '📌'
      }[n.notification_type] || '🔔';

      const pBadge = {
        HIGH: '<span class="px-2 py-0.5 rounded-full text-[9px] font-black bg-rose-100 text-rose-800">🔴 HIGH</span>',
        MEDIUM: '<span class="px-2 py-0.5 rounded-full text-[9px] font-black bg-amber-100 text-amber-800">🟡 MEDIUM</span>',
        LOW: '<span class="px-2 py-0.5 rounded-full text-[9px] font-black bg-slate-100 text-slate-700">🟢 INFO</span>',
      }[n.priority] || '';

      return `
        <div class="bg-white rounded-2xl border ${n.is_read ? 'border-slate-200 opacity-70' : 'border-slate-300 border-l-4 border-l-teal-600 shadow-sm'} p-4 transition-all hover:shadow-md">
          <div class="flex items-start space-x-3">
            <span class="text-2xl mt-0.5">${icon}</span>
            <div class="flex-1">
              <div class="flex items-center justify-between">
                <p class="text-xs font-black text-slate-900">${n.title}</p>
                <div class="flex items-center space-x-1.5">
                  ${pBadge}
                  ${!n.is_read ? '<span class="w-2 h-2 rounded-full bg-teal-600 flex-shrink-0"></span>' : ''}
                </div>
              </div>
              <p class="text-xs text-slate-600 mt-1 leading-relaxed">${n.message}</p>
              <div class="flex items-center justify-between mt-2 pt-2 border-t border-slate-100 text-[10px] text-slate-400 font-mono">
                <span>${new Date(n.created_at).toLocaleString('en-IN')}</span>
                ${!n.is_read ? `
                  <button onclick="markRead(${n.id}, this)" class="text-xs font-bold text-teal-700 hover:text-teal-900 font-sans">
                    ✓ Mark as read
                  </button>
                ` : '<span class="text-slate-400 font-sans">Read</span>'}
              </div>
            </div>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    if (list) list.innerHTML = `<div class="text-center py-8 text-rose-500 text-xs">Failed to load notifications.</div>`;
  }
}

async function markRead(notifId, el) {
  try {
    await API.markNotificationRead(notifId);
    Utils.showToast('Notification marked as read.', 'info');
    await loadNotifications();
  } catch (err) {
    Utils.showToast(err.message, 'error');
  }
}

async function markAllNotificationsRead() {
  try {
    await API.markAllNotificationsRead();
    Utils.showToast('All notifications marked as read.', 'success');
    await loadNotifications();
  } catch (err) {
    Utils.showToast(err.message, 'error');
  }
}

async function refreshNotificationAlerts() {
  try {
    const res = await API.triggerAutoNotifications();
    Utils.showToast(res.message, 'success');
    await loadNotifications();
  } catch (err) {
    Utils.showToast(err.message || 'Failed to refresh alerts.', 'error');
  }
}

// ─── Profile ──────────────────────────────────────────────────────────────────
async function loadProfile() {
  try {
    const me = await API.getMe();
    document.getElementById('profile-name').textContent = me.full_name || me.username;
    document.getElementById('profile-username').textContent = me.username;
    document.getElementById('profile-phone').textContent = me.phone || 'No phone set';
    document.getElementById('profile-avatar').textContent = (me.full_name || 'P')[0].toUpperCase();
  } catch (_) {}
}

async function handleChangePassword() {
  const current = document.getElementById('cp-current').value;
  const newPw = document.getElementById('cp-new').value;

  if (!current || !newPw) {
    Utils.showToast('Please fill in both password fields.', 'error');
    return;
  }
  if (newPw.length < 6) {
    Utils.showToast('New password must be at least 6 characters.', 'error');
    return;
  }

  try {
    await API.request('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password: current, new_password: newPw })
    });
    Utils.showToast('Password updated successfully!', 'success');
    document.getElementById('cp-current').value = '';
    document.getElementById('cp-new').value = '';
  } catch (err) {
    Utils.showToast(err.message || 'Failed to change password.', 'error');
  }
}

// Close modals on backdrop click
document.getElementById('vaccine-modal')?.addEventListener('click', function(e) {
  if (e.target === this) closeVaccineModal();
});
document.getElementById('edit-child-modal')?.addEventListener('click', function(e) {
  if (e.target === this) closeEditModal();
});
