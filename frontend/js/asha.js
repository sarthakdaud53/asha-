/**
 * Digital ASHA – ASHA Worker Field Operations Hub Controller (asha.js)
 * 
 * Delivers actionable field triage, priority follow-ups (HIGH/MEDIUM/LOW),
 * village registry, house visit logs, and comprehensive child profile operations.
 */

// ─── Global State ────────────────────────────────────────────────────────────
let currentUser = null;
let currentVillageChildren = [];
let currentPriorityItems = [];
let currentFamilies = [];
let currentHouseVisits = [];
let activeProfileChildId = null;
let activeProfileChildName = "";
let activeGrowthChildId = null;
let activeFollowUpChildId = null;
let activeCompleteVisitId = null;

// ─── Bootstrap ────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  const user = Auth.checkSession(['asha']);
  if (!user) return;
  currentUser = user;

  // Header display
  document.getElementById('asha-name').textContent = user.full_name || user.username;
  document.getElementById('asha-role').textContent = user.village_name ? `${user.village_name} Village` : 'Field Health Activist';
  document.getElementById('asha-avatar').textContent = (user.full_name || 'A')[0].toUpperCase();

  // Profile section display
  document.getElementById('prof-asha-name').textContent = user.full_name || user.username;
  document.getElementById('prof-asha-code').textContent = user.worker_code || 'ASHA-2026-001';
  document.getElementById('prof-asha-village').textContent = `Assigned Village: ${user.village_name || 'Rampur'}`;
  document.getElementById('prof-phone').textContent = user.phone || 'N/A';
  document.getElementById('prof-username').textContent = user.username;

  setupAshaFormListeners();

  // Initial load
  await Promise.all([
    loadAshaDashboard(),
    loadPriorityFollowUps('ALL'),
    loadChildrenRoster(),
    loadNotificationsAsha()
  ]);
});

// ─── Section Navigation ───────────────────────────────────────────────────────
function switchAshaSection(secName) {
  document.querySelectorAll('.section-view').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(el => el.classList.remove('active'));

  const sec = document.getElementById(`sec-${secName}`);
  if (sec) sec.classList.add('active');

  const nav = document.getElementById(`nav-${secName}`);
  if (nav) nav.classList.add('active');

  window.scrollTo({ top: 0, behavior: 'smooth' });

  // Section lazy loaders
  if (secName === 'dashboard') loadAshaDashboard();
  if (secName === 'priority-followups') loadPriorityFollowUps();
  if (secName === 'children') loadChildrenRoster();
  if (secName === 'families') loadFamilies();
  if (secName === 'vaccinations') loadVaccinationsOverview();
  if (secName === 'house-visits') loadHouseVisits();
  if (secName === 'reports') loadReports();
  if (secName === 'notifications') loadNotificationsAsha();
}

// ─── 1. Dashboard (8 Actionable Cards) ─────────────────────────────────────────
async function loadAshaDashboard() {
  try {
    const stats = await API.getAshaDashboard();

    document.getElementById('dash-village-title').textContent = `${stats.village_name} Village`;
    document.getElementById('dash-subcenter-subtitle').textContent = `Sub-Center: ${stats.sub_center} • Primary Health Centre: ${stats.phc_name}`;

    // 8 KPI Cards
    document.getElementById('card-families').textContent = stats.total_families || 0;
    document.getElementById('card-children').textContent = stats.total_children || 0;
    document.getElementById('card-completed').textContent = stats.vaccinations_completed || 0;
    document.getElementById('card-due').textContent = stats.vaccinations_due || 0;
    document.getElementById('card-overdue').textContent = stats.vaccinations_overdue || 0;
    document.getElementById('card-upcoming').textContent = stats.upcoming_vaccinations || 0;
    document.getElementById('card-pending-verify').textContent = stats.pending_verification || 0;
    document.getElementById('card-todays-followups').textContent = stats.todays_followups || 0;

    // Load preview of top priority items
    const priorityItems = await API.getPriorityFollowUps('HIGH');
    document.getElementById('btn-priority-count').textContent = priorityItems.length;

    const previewContainer = document.getElementById('dash-priority-preview');
    if (!priorityItems.length) {
      previewContainer.innerHTML = `
        <div class="py-6 text-center bg-emerald-50 rounded-2xl border border-emerald-200">
          <span class="text-2xl block mb-1">🎉</span>
          <p class="text-xs font-bold text-emerald-800">No Urgent Overdue Doses!</p>
          <p class="text-[11px] text-emerald-600">All registered children in this village are up to date on scheduled vaccinations.</p>
        </div>
      `;
    } else {
      previewContainer.innerHTML = priorityItems.slice(0, 3).map(item => `
        <div class="p-3.5 rounded-2xl border border-rose-200 bg-rose-50/60 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <div class="flex items-center space-x-2">
              <span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-rose-600 text-white">HIGH PRIORITY</span>
              <strong class="text-xs text-slate-900">${item.child_name}</strong>
              <span class="text-slate-500 text-[11px]">(${item.age_formatted})</span>
            </div>
            <p class="text-xs text-rose-800 font-medium mt-1">${item.reason}</p>
            <p class="text-[11px] text-slate-600 mt-0.5">Parent: ${item.parent_name} • Phone: ${item.parent_phone} • House: ${item.house_number}</p>
          </div>
          <div class="flex items-center space-x-2 shrink-0">
            <button onclick="openChildProfileModal(${item.child_id})" class="px-3 py-1.5 rounded-xl text-xs font-bold bg-white text-slate-800 border border-slate-300 hover:bg-slate-50">
              View Profile
            </button>
            <button onclick="Utils.sendWhatsApp('${item.parent_phone}', '${item.whatsapp_message.replace(/'/g, "\\'")}')" class="px-3 py-1.5 rounded-xl text-xs font-bold bg-emerald-600 text-white hover:bg-emerald-700">
              💬 WhatsApp
            </button>
          </div>
        </div>
      `).join('');
    }
  } catch (err) {
    console.error('Dashboard load failed:', err);
    Utils.showToast('Failed to load ASHA dashboard stats.', 'error');
  }
}

// ─── 2. Priority Follow-ups Triage (HIGH, MEDIUM, LOW) ────────────────────────
let currentSelectedPriority = 'ALL';

async function filterPriorityList(prio) {
  currentSelectedPriority = prio;
  ['all', 'high', 'medium', 'low'].forEach(p => {
    const btn = document.getElementById(`pf-tab-${p}`);
    if (btn) {
      if (p.toUpperCase() === prio || (p === 'all' && prio === 'ALL')) {
        btn.className = 'px-3.5 py-1.5 rounded-xl font-bold bg-white text-slate-900 shadow-sm';
      } else {
        btn.className = 'px-3.5 py-1.5 rounded-xl font-bold text-slate-600 hover:bg-white/50';
      }
    }
  });
  await loadPriorityFollowUps(prio === 'ALL' ? '' : prio);
}

async function loadPriorityFollowUps(priority = '') {
  const tbody = document.getElementById('priority-followup-tbody');
  tbody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-slate-400">Loading priority list...</td></tr>`;

  try {
    const items = await API.getPriorityFollowUps(priority);
    currentPriorityItems = items;

    if (!items.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="py-10 text-center">
            <p class="text-3xl mb-2">🎉</p>
            <p class="text-xs font-bold text-slate-700">No priority actions in this category</p>
            <p class="text-[11px] text-slate-400 mt-0.5">All children in ${currentUser.village_name || 'the village'} are up to date.</p>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = items.map(item => {
      const pBadge = {
        HIGH: '<span class="px-2.5 py-1 rounded-full text-[10px] font-black bg-rose-100 text-rose-800 border border-rose-200">🔴 HIGH</span>',
        MEDIUM: '<span class="px-2.5 py-1 rounded-full text-[10px] font-black bg-amber-100 text-amber-800 border border-amber-200">🟡 MEDIUM</span>',
        LOW: '<span class="px-2.5 py-1 rounded-full text-[10px] font-black bg-sky-100 text-sky-800 border border-sky-200">🟢 LOW</span>',
      }[item.priority] || '<span class="px-2 py-0.5 rounded text-xs bg-slate-100">ROUTINE</span>';

      return `
        <tr class="border-b border-slate-100 hover:bg-slate-50/80 transition-colors">
          <td class="py-3.5 px-3.5">${pBadge}</td>
          <td class="py-3.5 px-3.5">
            <div class="font-black text-slate-900">${item.child_name}</div>
            <div class="text-[11px] text-slate-500">${item.age_formatted}</div>
          </td>
          <td class="py-3.5 px-3.5">
            <div class="font-semibold text-slate-800">${item.parent_name}</div>
            <a href="tel:${item.parent_phone}" class="text-[11px] text-teal-700 font-mono underline">${item.parent_phone}</a>
          </td>
          <td class="py-3.5 px-3.5 text-slate-600">
            <div>House #${item.house_number}</div>
            <div class="text-[11px] text-slate-400">${item.village_name}</div>
          </td>
          <td class="py-3.5 px-3.5 max-w-xs">
            <p class="font-medium text-slate-800">${item.reason}</p>
          </td>
          <td class="py-3.5 px-3.5 font-mono text-slate-600">
            ${new Date(item.due_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
            ${item.overdue_days > 0 ? `<div class="text-[10px] font-bold text-rose-600">${item.overdue_days}d overdue</div>` : ''}
          </td>
          <td class="py-3.5 px-3.5 text-right space-x-1 whitespace-nowrap">
            <button onclick="openChildProfileModal(${item.child_id})" class="px-2.5 py-1.5 rounded-xl font-bold bg-teal-50 text-teal-800 border border-teal-200 hover:bg-teal-100" title="Open Child Profile">
              👤 Profile
            </button>
            <button onclick="Utils.sendWhatsApp('${item.parent_phone}', '${item.whatsapp_message.replace(/'/g, "\\'")}')" class="px-2.5 py-1.5 rounded-xl font-bold bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm" title="Send WhatsApp Reminder">
              💬
            </button>
            <a href="tel:${item.parent_phone}" class="p-2 rounded-xl font-bold bg-slate-100 hover:bg-slate-200 text-slate-700 inline-block align-middle" title="Call Parent">
              📞
            </a>
            <button onclick="openFollowUpModal(${item.child_id}, '${item.child_name.replace(/'/g, "\\'")}')" class="px-2.5 py-1.5 rounded-xl font-bold bg-slate-100 hover:bg-slate-200 text-slate-700" title="Schedule Visit">
              🏡
            </button>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="py-6 text-center text-rose-500">Failed to load priority items.</td></tr>`;
  }
}

// ─── 3. Children Register ─────────────────────────────────────────────────────
let searchDebounceTimeout = null;
function debounceChildrenSearch() {
  clearTimeout(searchDebounceTimeout);
  searchDebounceTimeout = setTimeout(() => {
    loadChildrenRoster();
  }, 300);
}

async function loadChildrenRoster() {
  const tbody = document.getElementById('children-roster-tbody');
  tbody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-slate-400">Loading children...</td></tr>`;

  try {
    const search = document.getElementById('children-search-input')?.value || '';
    const statusFilter = document.getElementById('children-status-filter')?.value || '';

    const params = {};
    if (search) params.search = search;
    if (statusFilter) params.status_filter = statusFilter;

    currentVillageChildren = await API.getChildren(params);

    if (!currentVillageChildren.length) {
      tbody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-slate-400">No children matching filters.</td></tr>`;
      return;
    }

    tbody.innerHTML = currentVillageChildren.map(c => {
      const vBadge = c.is_verified
        ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">✓ Verified</span>'
        : '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800">⏳ Pending Verification</span>';

      return `
        <tr class="border-b border-slate-100 hover:bg-slate-50/80 transition-colors">
          <td class="py-3 px-3.5">
            <div class="font-black text-slate-900 cursor-pointer hover:text-teal-700" onclick="openChildProfileModal(${c.id})">${c.full_name}</div>
            <div class="text-[11px] text-slate-500 font-mono">${c.rch_mcp_number || 'Pending ID'}</div>
          </td>
          <td class="py-3 px-3.5 text-slate-700">
            <div>${c.age_formatted}</div>
            <div class="text-[11px] text-slate-400">${new Date(c.date_of_birth).toLocaleDateString('en-IN')} (${c.gender})</div>
          </td>
          <td class="py-3 px-3.5 text-slate-700">
            <div>${c.parent_name}</div>
            <div class="text-[11px] text-slate-500 font-mono">${c.parent_phone}</div>
          </td>
          <td class="py-3 px-3.5">
            <div class="flex items-center space-x-2">
              <div class="w-16 bg-slate-200 rounded-full h-2 overflow-hidden">
                <div class="bg-teal-600 h-full rounded-full" style="width: ${c.immunization_rate}%"></div>
              </div>
              <span class="text-xs font-bold text-slate-800">${c.immunization_rate}%</span>
            </div>
            <div class="text-[10px] text-slate-400 mt-0.5">${c.completed_vaccines}/${c.total_vaccines} doses</div>
          </td>
          <td class="py-3 px-3.5">
            ${c.overdue_vaccines > 0
              ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-200">⚠️ ${c.overdue_vaccines} Overdue</span>`
              : c.due_vaccines > 0
              ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">🔔 Due Now</span>`
              : `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">✓ On Track</span>`}
            <div class="mt-1">${vBadge}</div>
          </td>
          <td class="py-3 px-3.5">
            ${Utils.getNutritionBadge(c.latest_nutritional_status)}
          </td>
          <td class="py-3 px-3.5 text-right space-x-1 whitespace-nowrap">
            <button onclick="openChildProfileModal(${c.id})" class="px-2.5 py-1.5 rounded-xl font-bold bg-teal-600 text-white hover:bg-teal-700 shadow-sm" title="View Full Profile">
              👤 Profile
            </button>
            <button onclick="openAdministerModal(${c.id})" class="px-2.5 py-1.5 rounded-xl font-bold bg-teal-50 text-teal-800 border border-teal-200 hover:bg-teal-100" title="Log Vaccine Dose">
              💉 Dose
            </button>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="py-6 text-center text-rose-500">Failed to load child register.</td></tr>`;
  }
}

// ─── 4. Families ──────────────────────────────────────────────────────────────
async function loadFamilies() {
  const tbody = document.getElementById('families-tbody');
  tbody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-slate-400">Loading families...</td></tr>`;

  try {
    const families = await API.getAshaFamilies();
    currentFamilies = families;

    if (!families.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-slate-400">No families registered yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = families.map(f => `
      <tr class="border-b border-slate-100 hover:bg-slate-50 transition-colors">
        <td class="py-3.5 px-3.5 font-bold text-slate-900">${f.family_head_name}</td>
        <td class="py-3.5 px-3.5 text-slate-700">House #${f.house_number || 'N/A'}, ${f.address || f.village_name}</td>
        <td class="py-3.5 px-3.5 font-mono text-teal-800 font-bold">${f.contact_number || '-'}</td>
        <td class="py-3.5 px-3.5"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-700">${f.socioeconomic_category || 'General'}</span></td>
        <td class="py-3.5 px-3.5 font-bold text-slate-800">${f.total_children}</td>
        <td class="py-3.5 px-3.5 text-right text-slate-500 font-mono">${new Date(f.created_at).toLocaleDateString('en-IN')}</td>
      </tr>
    `).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="py-6 text-center text-rose-500">Failed to load families.</td></tr>`;
  }
}

// ─── 5. Vaccinations Overview ─────────────────────────────────────────────────
async function loadVaccinationsOverview() {
  const grid = document.getElementById('vaccine-category-summary-grid');
  grid.innerHTML = `<div class="text-center py-6 text-slate-400 text-xs col-span-3">Loading UIP schedule overview...</div>`;

  try {
    const vaccines = await API.getVaccines();
    const categories = {};

    vaccines.forEach(v => {
      const cat = v.category || 'General';
      if (!categories[cat]) categories[cat] = [];
      categories[cat].push(v);
    });

    grid.innerHTML = Object.entries(categories).map(([cat, vacs]) => `
      <div class="p-4 rounded-2xl border border-slate-200 bg-slate-50/50 space-y-2">
        <div class="flex items-center justify-between border-b border-slate-200 pb-2">
          <h4 class="font-black text-xs text-teal-900 uppercase tracking-wider">${cat}</h4>
          <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-teal-100 text-teal-800">${vacs.length} Doses</span>
        </div>
        <div class="space-y-1.5 pt-1">
          ${vacs.map(v => `
            <div class="flex items-center justify-between text-xs py-1">
              <span class="font-semibold text-slate-800">${v.vaccine_name}</span>
              <span class="text-[11px] text-slate-500">${v.recommended_timing}</span>
            </div>
          `).join('')}
        </div>
      </div>
    `).join('');
  } catch (err) {
    grid.innerHTML = `<div class="text-center py-6 text-rose-500 text-xs col-span-3">Failed to load vaccine categories.</div>`;
  }
}

// ─── 6. House Visits Management System ────────────────────────────────────────
let currentVisitCategory = 'today';
let activeRescheduleVisitId = null;

function switchVisitCategory(cat) {
  currentVisitCategory = cat;
  ['today', 'upcoming', 'pending', 'completed'].forEach(c => {
    const btn = document.getElementById(`vtab-${c}`);
    if (btn) {
      if (c === cat) {
        btn.className = 'px-3.5 py-2 rounded-xl font-bold bg-white text-slate-900 shadow-sm flex items-center space-x-1.5 whitespace-nowrap';
      } else {
        btn.className = 'px-3.5 py-2 rounded-xl font-bold text-slate-600 hover:bg-white/50 flex items-center space-x-1.5 whitespace-nowrap';
      }
    }
  });
  loadHouseVisits();
}

async function loadHouseVisits() {
  const tbody = document.getElementById('house-visits-tbody');
  tbody.innerHTML = `<tr><td colspan="8" class="py-8 text-center text-slate-400">Loading house visits...</td></tr>`;

  try {
    // 1. Fetch live count badges
    const counts = await API.getAshaHouseVisitCounts();
    if (document.getElementById('vcount-today')) document.getElementById('vcount-today').textContent = counts.today || 0;
    if (document.getElementById('vcount-upcoming')) document.getElementById('vcount-upcoming').textContent = counts.upcoming || 0;
    if (document.getElementById('vcount-pending')) document.getElementById('vcount-pending').textContent = counts.pending || 0;
    if (document.getElementById('vcount-completed')) document.getElementById('vcount-completed').textContent = counts.completed || 0;

    // 2. Fetch category list
    const priority = document.getElementById('visit-priority-filter')?.value || '';
    const params = { category: currentVisitCategory };
    if (priority) params.priority = priority;

    const visits = await API.getAshaHouseVisits(params);
    currentHouseVisits = visits;

    if (!visits.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" class="py-10 text-center">
            <p class="text-3xl mb-2">🎉</p>
            <p class="text-xs font-bold text-slate-700">No ${currentVisitCategory} visits recorded</p>
            <p class="text-[11px] text-slate-400 mt-0.5">Use the "Auto-Plan Targeted Visits" button to generate priority-targeted visits.</p>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = visits.map(v => {
      const isCompleted = v.status === 'completed';
      const isRescheduled = v.status === 'rescheduled';

      const pBadge = {
        HIGH: '<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-rose-100 text-rose-800 border border-rose-200">🔴 HIGH</span>',
        MEDIUM: '<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-amber-100 text-amber-800 border border-amber-200">🟡 MEDIUM</span>',
        LOW: '<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-sky-100 text-sky-800 border border-sky-200">🟢 LOW</span>',
      }[v.priority] || '<span class="px-2 py-0.5 rounded text-xs bg-slate-100">ROUTINE</span>';

      const stBadge = isCompleted
        ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">✓ Completed</span>'
        : isRescheduled
        ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 text-purple-800">📅 Rescheduled</span>'
        : '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800">⏳ Scheduled</span>';

      return `
        <tr class="border-b border-slate-100 hover:bg-slate-50 transition-colors">
          <td class="py-3 px-3.5">${pBadge}</td>
          <td class="py-3 px-3.5">
            <div class="font-black text-slate-900 cursor-pointer hover:text-teal-700" onclick="openChildProfileModal(${v.child_id})">${v.child_name}</div>
            <div class="text-[11px] text-slate-500">House #${v.house_number || 'N/A'} • ${v.family_head_name || 'Family'}</div>
          </td>
          <td class="py-3 px-3.5 font-mono text-slate-700 font-semibold">
            ${new Date(v.visit_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
          </td>
          <td class="py-3 px-3.5 font-medium text-slate-800 max-w-xs">
            ${v.reason}
          </td>
          <td class="py-3 px-3.5">${stBadge}</td>
          <td class="py-3 px-3.5 text-slate-600 max-w-xs">
            <div>${v.remarks || '-'}</div>
            ${v.observations ? `<div class="text-[10px] text-teal-800 mt-0.5 font-medium">Obs: ${v.observations}</div>` : ''}
            ${v.notes ? `<div class="text-[10px] text-slate-400 mt-0.5 italic">${v.notes}</div>` : ''}
          </td>
          <td class="py-3 px-3.5 font-mono text-slate-500 text-[11px]">
            ${v.completed_at ? new Date(v.completed_at).toLocaleString('en-IN') : '-'}
          </td>
          <td class="py-3 px-3.5 text-right space-x-1 whitespace-nowrap">
            ${!isCompleted ? `
              <button onclick="openCompleteVisitModal(${v.id})" class="px-2.5 py-1.5 rounded-xl text-xs font-bold bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm" title="Mark Completed">
                ✓ Done
              </button>
              <button onclick="openRescheduleVisitModal(${v.id}, '${v.visit_date}')" class="px-2.5 py-1.5 rounded-xl text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-700" title="Reschedule Visit">
                📅 Reschedule
              </button>
            ` : '<span class="text-emerald-700 font-bold text-xs">Logged ✓</span>'}
            <button onclick="openChildProfileModal(${v.child_id})" class="p-1.5 rounded-xl text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-700 inline-block align-middle" title="Open Profile">
              👤
            </button>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" class="py-6 text-center text-rose-500">Failed to load house visits.</td></tr>`;
  }
}

async function runSmartVisitPlanner() {
  try {
    const res = await API.generateSmartVisitPlan();
    Utils.showToast(res.message, 'success');
    await loadHouseVisits();
    await loadAshaDashboard();
  } catch (err) {
    Utils.showToast(err.message || 'Failed to run smart visit planner.', 'error');
  }
}

function openCompleteVisitModal(visitId) {
  activeCompleteVisitId = visitId;
  document.getElementById('complete-visit-modal').classList.remove('hidden');
}

function closeCompleteVisitModal() {
  document.getElementById('complete-visit-modal').classList.add('hidden');
  activeCompleteVisitId = null;
}

function openRescheduleVisitModal(visitId, currentVisitDate) {
  activeRescheduleVisitId = visitId;
  document.getElementById('resched-new-date').value = currentVisitDate || new Date().toISOString().split('T')[0];
  document.getElementById('reschedule-visit-modal').classList.remove('hidden');
}

function closeRescheduleVisitModal() {
  document.getElementById('reschedule-visit-modal').classList.add('hidden');
  activeRescheduleVisitId = null;
}

// ─── 7. Reports ───────────────────────────────────────────────────────────────
async function loadReports() {
  const container = document.getElementById('report-content');
  container.innerHTML = `<div class="text-center py-8 text-slate-400 text-xs">Generating monthly report...</div>`;

  try {
    const report = await API.getAshaReports();
    const sum = report.summary || {};

    container.innerHTML = `
      <div class="p-6 bg-slate-50 rounded-2xl border border-slate-200 space-y-5">
        <div class="border-b border-slate-200 pb-3">
          <span class="text-xs font-bold uppercase text-teal-800">Ministry of Health & Family Welfare</span>
          <h3 class="text-lg font-black text-slate-900 mt-0.5">Village Immunization & Growth Progress Report</h3>
          <p class="text-xs text-slate-500">Village: <strong>${report.village_name}</strong> • Sub-Center: ${report.sub_center} • PHC: ${report.phc_name} • Date: ${new Date(report.generated_on).toLocaleDateString('en-IN')}</p>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div class="p-3 bg-white rounded-xl border border-slate-200 text-center">
            <span class="text-[10px] font-bold text-slate-500 uppercase block">Registered Children</span>
            <span class="text-2xl font-black text-slate-900">${sum.total_registered_children || 0}</span>
          </div>
          <div class="p-3 bg-emerald-50 rounded-xl border border-emerald-200 text-center">
            <span class="text-[10px] font-bold text-emerald-800 uppercase block">Fully Immunized</span>
            <span class="text-2xl font-black text-emerald-700">${sum.fully_immunized || 0}</span>
          </div>
          <div class="p-3 bg-amber-50 rounded-xl border border-amber-200 text-center">
            <span class="text-[10px] font-bold text-amber-800 uppercase block">Partially Immunized</span>
            <span class="text-2xl font-black text-amber-700">${sum.partially_immunized || 0}</span>
          </div>
          <div class="p-3 bg-teal-50 rounded-xl border border-teal-200 text-center">
            <span class="text-[10px] font-bold text-teal-800 uppercase block">Coverage Rate</span>
            <span class="text-2xl font-black text-teal-700">${sum.coverage_percentage || 0}%</span>
          </div>
        </div>

        <!-- UIP Category Breakdown Table -->
        <div class="space-y-2 pt-2">
          <h4 class="text-xs font-bold text-slate-800 uppercase tracking-wider">UIP Category Performance</h4>
          <table class="w-full text-left border-collapse text-xs bg-white rounded-xl overflow-hidden border border-slate-200">
            <thead>
              <tr class="bg-slate-100 text-slate-600 font-bold border-b border-slate-200">
                <th class="p-2.5">Category</th>
                <th class="p-2.5">Scheduled Doses</th>
                <th class="p-2.5">Administered</th>
                <th class="p-2.5">Overdue Cases</th>
              </tr>
            </thead>
            <tbody>
              ${Object.entries(report.category_breakdown || {}).map(([cat, st]) => `
                <tr class="border-b border-slate-100">
                  <td class="p-2.5 font-bold">${cat}</td>
                  <td class="p-2.5">${st.scheduled}</td>
                  <td class="p-2.5 font-bold text-emerald-700">${st.administered}</td>
                  <td class="p-2.5 font-bold ${st.overdue > 0 ? 'text-rose-700' : 'text-slate-400'}">${st.overdue}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div class="text-center py-8 text-rose-500 text-xs">Failed to generate report.</div>`;
  }
}

// ─── 8. Notifications & Field Alerts ──────────────────────────────────────────
let currentAshaNotifFilter = 'all';

function filterAshaNotifications(filter) {
  currentAshaNotifFilter = filter;
  ['all', 'unread', 'high'].forEach(f => {
    const btn = document.getElementById(`asha-notif-pill-${f}`);
    if (btn) {
      if (f === filter.toLowerCase()) {
        btn.className = 'px-3.5 py-1.5 rounded-full font-bold bg-teal-600 text-white shadow-sm';
      } else {
        btn.className = 'px-3.5 py-1.5 rounded-full font-bold bg-slate-100 text-slate-700 hover:bg-slate-200';
      }
    }
  });
  loadNotificationsAsha();
}

async function loadNotificationsAsha() {
  const container = document.getElementById('asha-notifications-list');
  if (container) container.innerHTML = `<div class="text-center py-8 text-slate-400 text-xs">Loading alerts...</div>`;

  try {
    const params = {};
    if (currentAshaNotifFilter === 'unread') params.is_read = false;
    if (currentAshaNotifFilter === 'HIGH') params.priority = 'HIGH';

    const notes = await API.getNotifications(params);
    const unreadRes = await API.getUnreadNotificationCount();
    const unread = unreadRes.unread_count || 0;

    const badge = document.getElementById('notif-badge-asha');
    if (badge) {
      if (unread > 0) {
        badge.textContent = unread > 9 ? '9+' : unread;
        badge.classList.remove('hidden');
      } else {
        badge.classList.add('hidden');
      }
    }

    const unreadPill = document.getElementById('asha-unread-badge');
    if (unreadPill) unreadPill.textContent = unread;

    if (!container) return;

    if (!notes.length) {
      container.innerHTML = `
        <div class="py-10 text-center">
          <p class="text-3xl mb-2">🎉</p>
          <p class="text-xs font-bold text-slate-700">No field alerts right now</p>
          <p class="text-[11px] text-slate-400 mt-0.5">All child immunizations and verification tasks in your village are on track.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = notes.map(n => {
      const icon = {
        new_child_registration: '👶',
        vaccine_overdue: '⚠️',
        priority_followup: '⚡',
        parent_updated_info: '✏️',
        verification_required: '📋',
        asha_followup: '🏡',
        general: '📌'
      }[n.notification_type] || '🔔';

      const pBadge = {
        HIGH: '<span class="px-2 py-0.5 rounded-full text-[9px] font-black bg-rose-100 text-rose-800 border border-rose-200">🔴 HIGH</span>',
        MEDIUM: '<span class="px-2 py-0.5 rounded-full text-[9px] font-black bg-amber-100 text-amber-800 border border-amber-200">🟡 MEDIUM</span>',
        LOW: '<span class="px-2 py-0.5 rounded-full text-[9px] font-black bg-slate-100 text-slate-700">🟢 LOW</span>',
      }[n.priority] || '';

      return `
        <div class="p-4 rounded-2xl border ${n.is_read ? 'bg-white opacity-70 border-slate-200' : 'bg-teal-50/40 border-teal-300 border-l-4 border-l-teal-600 shadow-sm'} transition-all hover:shadow-md">
          <div class="flex items-start space-x-3">
            <span class="text-2xl mt-0.5">${icon}</span>
            <div class="flex-1">
              <div class="flex items-center justify-between">
                <h4 class="font-bold text-xs text-slate-900">${n.title}</h4>
                <div class="flex items-center space-x-1.5">
                  ${pBadge}
                  ${!n.is_read ? '<span class="w-2 h-2 rounded-full bg-teal-600 flex-shrink-0"></span>' : ''}
                </div>
              </div>
              <p class="text-xs text-slate-600 mt-1 leading-relaxed">${n.message}</p>
              <div class="flex items-center justify-between mt-2 pt-2 border-t border-slate-100 text-[10px] text-slate-400 font-mono">
                <span>${new Date(n.created_at).toLocaleString('en-IN')}</span>
                <div class="flex items-center space-x-2">
                  ${!n.is_read ? `
                    <button onclick="markNotificationReadAsha(${n.id}, this)" class="text-xs font-bold text-teal-800 hover:text-teal-950 font-sans">
                      ✓ Mark read
                    </button>
                  ` : '<span class="text-slate-400 font-sans">Read</span>'}
                </div>
              </div>
            </div>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    if (container) container.innerHTML = `<div class="text-center py-8 text-rose-500 text-xs">Failed to load alerts.</div>`;
  }
}

async function markNotificationReadAsha(id, el) {
  try {
    await API.markNotificationRead(id);
    Utils.showToast('Alert marked as read.', 'info');
    await loadNotificationsAsha();
  } catch (err) {
    Utils.showToast(err.message, 'error');
  }
}

async function markAllAshaNotificationsRead() {
  try {
    await API.markAllNotificationsRead();
    Utils.showToast('All alerts marked as read.', 'success');
    await loadNotificationsAsha();
  } catch (err) {
    Utils.showToast(err.message, 'error');
  }
}

async function refreshAshaNotificationAlerts() {
  try {
    const res = await API.triggerAutoNotifications();
    Utils.showToast(res.message, 'success');
    await loadNotificationsAsha();
    await loadAshaDashboard();
  } catch (err) {
    Utils.showToast(err.message || 'Failed to scan alerts.', 'error');
  }
}

// ─── 9. Comprehensive Child Profile Modal ─────────────────────────────────────
async function openChildProfileModal(childId) {
  activeProfileChildId = childId;
  const modal = document.getElementById('child-profile-modal');
  modal.classList.remove('hidden');

  try {
    const child = await API.getChildDetail(childId);
    activeProfileChildName = child.full_name;

    // Header Info
    document.getElementById('cp-modal-child-name').textContent = child.full_name;
    document.getElementById('cp-modal-meta').textContent = `Age: ${child.age_formatted} • MCP: ${child.rch_mcp_number || 'Pending'} • Village: ${child.village_name}`;

    const vBadge = document.getElementById('cp-modal-verify-badge');
    const vBtn = document.getElementById('cp-btn-verify');
    if (child.is_verified) {
      vBadge.textContent = '✓ Verified by ASHA';
      vBadge.className = 'px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-400 text-slate-900';
      vBtn.classList.add('hidden');
    } else {
      vBadge.textContent = '⏳ Pending Verification';
      vBadge.className = 'px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-400 text-slate-900';
      vBtn.classList.remove('hidden');
    }

    // Metrics
    document.getElementById('cp-m-total').textContent = child.total_vaccines;
    document.getElementById('cp-m-completed').textContent = child.completed_vaccines;
    document.getElementById('cp-m-due').textContent = child.due_vaccines;
    document.getElementById('cp-m-overdue').textContent = child.overdue_vaccines;

    // Child Details
    document.getElementById('cp-f-dob').textContent = `${new Date(child.date_of_birth).toLocaleDateString('en-IN')} (${child.gender})`;
    document.getElementById('cp-f-weight').textContent = child.birth_weight_kg ? `${child.birth_weight_kg} kg` : 'Not recorded';
    document.getElementById('cp-f-blood').textContent = child.blood_group || 'Not recorded';
    document.getElementById('cp-f-place').textContent = child.birth_place || 'PHC';
    document.getElementById('cp-f-nutrition').textContent = child.latest_nutritional_status || 'Normal';

    // Parent Details
    document.getElementById('cp-f-mother').textContent = child.mother_name || 'Not recorded';
    document.getElementById('cp-f-father').textContent = child.father_name || 'Not recorded';
    document.getElementById('cp-f-phone').textContent = child.parent_contact || child.parent_phone || 'No phone';
    document.getElementById('cp-f-house').textContent = child.house_number || 'N/A';
    document.getElementById('cp-f-village').textContent = child.village_name;

    // UIP Timeline Table
    const timelineTbody = document.getElementById('cp-timeline-tbody');
    const vaccines = child.immunizations || child.vaccinations || [];
    if (!vaccines.length) {
      timelineTbody.innerHTML = `<tr><td colspan="7" class="py-4 text-center text-slate-400">No vaccination schedule found.</td></tr>`;
    } else {
      timelineTbody.innerHTML = vaccines.map(v => {
        const isAdm = v.status === 'administered';
        const isOd = v.status === 'overdue';
        const isDue = v.status === 'due';

        const stBadge = isAdm
          ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">Completed</span>'
          : isOd
          ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800">Overdue (${v.days_overdue}d)</span>`
          : isDue
          ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800">Due Now</span>'
          : '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-100 text-sky-800">Upcoming</span>';

        return `
          <tr class="border-b border-slate-100 ${isAdm ? 'bg-emerald-50/30' : isOd ? 'bg-rose-50/30' : ''}">
            <td class="py-2.5 px-3 font-bold text-slate-900">${v.vaccine_name}</td>
            <td class="py-2.5 px-3 text-slate-600">${v.category}</td>
            <td class="py-2.5 px-3 font-mono text-slate-600">${new Date(v.scheduled_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</td>
            <td class="py-2.5 px-3">${stBadge}</td>
            <td class="py-2.5 px-3 font-mono font-bold ${isAdm ? 'text-emerald-700' : 'text-slate-400'}">
              ${v.administered_date ? new Date(v.administered_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '-'}
            </td>
            <td class="py-2.5 px-3 text-slate-600">
              ${v.batch_number ? `<div class="font-mono text-[11px]">${v.batch_number}</div>` : ''}
              <div class="text-[10px] text-slate-400">${v.session_site || ''}</div>
            </td>
            <td class="py-2.5 px-3 text-right">
              ${!isAdm ? `
                <button onclick="openDirectAdministerModal(${v.id}, '${v.vaccine_name.replace(/'/g, "\\'")}', '${child.full_name.replace(/'/g, "\\'")}')" class="px-2 py-1 rounded-lg text-[11px] font-bold bg-teal-600 text-white hover:bg-teal-700">
                  Log Given
                </button>
              ` : '<span class="text-emerald-600 font-bold text-[11px]">✓ Done</span>'}
            </td>
          </tr>
        `;
      }).join('');
    }

    // House Visits History for this child
    const visitsContainer = document.getElementById('cp-visits-list');
    const childVisits = await API.getAshaHouseVisits();
    const relevantVisits = childVisits.filter(v => v.child_id === childId);

    if (!relevantVisits.length) {
      visitsContainer.innerHTML = `<div class="text-center py-4 text-slate-400">No house visits recorded for this child yet.</div>`;
    } else {
      visitsContainer.innerHTML = relevantVisits.map(v => `
        <div class="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1">
          <div class="flex justify-between items-center">
            <span class="font-bold text-slate-900">${v.reason}</span>
            <span class="font-mono text-[10px] text-slate-500">${new Date(v.visit_date).toLocaleDateString('en-IN')}</span>
          </div>
          <p class="text-slate-600">${v.remarks || 'No notes entered.'}</p>
          ${v.action_taken ? `<p class="text-[11px] text-teal-800 font-semibold">Action: ${v.action_taken}</p>` : ''}
        </div>
      `).join('');
    }

  } catch (err) {
    Utils.showToast('Failed to load child profile.', 'error');
  }
}

function closeChildProfileModal() {
  document.getElementById('child-profile-modal').classList.add('hidden');
  activeProfileChildId = null;
}

// ─── 10. Verification Action ──────────────────────────────────────────────────
async function verifyCurrentChild() {
  if (!activeProfileChildId) return;
  try {
    await API.verifyChild(activeProfileChildId);
    Utils.showToast('Child registration verified successfully!', 'success');
    await openChildProfileModal(activeProfileChildId);
    await loadAshaDashboard();
    await loadChildrenRoster();
    await loadPriorityFollowUps(currentSelectedPriority === 'ALL' ? '' : currentSelectedPriority);
  } catch (err) {
    Utils.showToast(err.message, 'error');
  }
}

// ─── 11. Update Permitted Fields Modal ────────────────────────────────────────
async function openEditChildFieldsModal() {
  if (!activeProfileChildId) return;
  try {
    const child = await API.getChildDetail(activeProfileChildId);
    document.getElementById('ef-house').value = child.house_number || '';
    document.getElementById('ef-phone').value = child.parent_contact || child.parent_phone || '';
    document.getElementById('ef-mother').value = child.mother_name || '';
    document.getElementById('ef-father').value = child.father_name || '';
    document.getElementById('ef-weight').value = child.birth_weight_kg || '';
    document.getElementById('ef-notes').value = child.notes || '';
    document.getElementById('edit-fields-modal').classList.remove('hidden');
  } catch (err) {
    Utils.showToast('Failed to load child details for edit.', 'error');
  }
}

function closeEditFieldsModal() {
  document.getElementById('edit-fields-modal').classList.add('hidden');
}

// ─── 12. Modal Handlers (Administer, Growth, House Visit) ──────────────────────
async function openAdministerModal(childId) {
  const modal = document.getElementById('administer-modal');
  modal.classList.remove('hidden');

  const child = await API.getChildDetail(childId);
  document.getElementById('administer-child-name').textContent = `${child.full_name} (${child.age_formatted})`;

  const select = document.getElementById('administer-vaccine-select');
  const pendingVacs = (child.immunizations || child.vaccinations || []).filter(v => v.status !== 'administered');

  if (!pendingVacs.length) {
    select.innerHTML = '<option value="">All vaccines already administered!</option>';
  } else {
    select.innerHTML = pendingVacs.map(v => `
      <option value="${v.id}">${v.vaccine_name} [${v.category}] - ${v.status.toUpperCase()}</option>
    `).join('');
  }

  document.getElementById('administer-date').value = new Date().toISOString().split('T')[0];
  document.getElementById('administer-session-site').value = `${child.village_name} Anganwadi Center / PHC`;
}

function openDirectAdministerModal(recordId, vaccineName, childName) {
  const modal = document.getElementById('administer-modal');
  modal.classList.remove('hidden');
  document.getElementById('administer-child-name').textContent = childName;

  const select = document.getElementById('administer-vaccine-select');
  select.innerHTML = `<option value="${recordId}" selected>${vaccineName}</option>`;

  document.getElementById('administer-date').value = new Date().toISOString().split('T')[0];
  document.getElementById('administer-session-site').value = `${currentUser.village_name || 'Village'} Anganwadi Center / Sub-Center`;
}

function closeAdministerModal() {
  document.getElementById('administer-modal').classList.add('hidden');
}

function openGrowthModal(childId, childName) {
  activeGrowthChildId = childId;
  document.getElementById('growth-modal').classList.remove('hidden');
  document.getElementById('growth-child-name').textContent = childName;
  document.getElementById('growth-date').value = new Date().toISOString().split('T')[0];
}

function closeGrowthModal() {
  document.getElementById('growth-modal').classList.add('hidden');
}

function openFollowUpModal(childId, childName) {
  activeFollowUpChildId = childId || (currentVillageChildren.length ? currentVillageChildren[0].id : null);
  const modal = document.getElementById('followup-note-modal');
  modal.classList.remove('hidden');

  // Populate children select
  const select = document.getElementById('followup-child-select');
  if (select && currentVillageChildren.length) {
    select.innerHTML = currentVillageChildren.map(c => `
      <option value="${c.id}" ${c.id === activeFollowUpChildId ? 'selected' : ''}>${c.full_name} (House #${c.house_number || 'N/A'})</option>
    `).join('');
  }

  document.getElementById('followup-child-name').textContent = childName || (currentVillageChildren.length ? currentVillageChildren[0].full_name : 'Selected Child');
  document.getElementById('followup-date').value = new Date().toISOString().split('T')[0];
}

function openNewVisitModal() {
  if (currentVillageChildren.length > 0) {
    openFollowUpModal(currentVillageChildren[0].id, currentVillageChildren[0].full_name);
  } else {
    Utils.showToast('Please register or select a child from the Children register.', 'info');
  }
}

function closeFollowUpModal() {
  document.getElementById('followup-note-modal').classList.add('hidden');
}

// ─── 13. Form Submissions ─────────────────────────────────────────────────────
function setupAshaFormListeners() {
  // 1. Administer Vaccine Form
  const admForm = document.getElementById('administer-vaccine-form');
  if (admForm) {
    admForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const recordId = document.getElementById('administer-vaccine-select').value;
      if (!recordId) {
        Utils.showToast('Please select a vaccine to record', 'error');
        return;
      }

      const payload = {
        administered_date: document.getElementById('administer-date').value,
        batch_number: document.getElementById('administer-batch').value || 'VAC-2026',
        session_site: document.getElementById('administer-session-site').value,
        aefi_reported: document.getElementById('administer-aefi-toggle').checked,
        aefi_details: document.getElementById('administer-aefi-notes').value || null,
        notes: document.getElementById('administer-notes').value || null
      };

      try {
        await API.administerVaccine(recordId, payload);
        Utils.showToast('Vaccination dose logged successfully! Audit trail updated.', 'success');
        closeAdministerModal();
        admForm.reset();

        // Refresh views
        if (activeProfileChildId) await openChildProfileModal(activeProfileChildId);
        await loadAshaDashboard();
        await loadChildrenRoster();
        await loadPriorityFollowUps(currentSelectedPriority === 'ALL' ? '' : currentSelectedPriority);
      } catch (err) {
        Utils.showToast(err.message, 'error');
      }
    });
  }

  // 2. Growth Form
  const growthForm = document.getElementById('record-growth-form');
  if (growthForm) {
    growthForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!activeGrowthChildId) return;

      const payload = {
        recorded_date: document.getElementById('growth-date').value,
        weight_kg: parseFloat(document.getElementById('growth-weight').value),
        height_cm: document.getElementById('growth-height').value ? parseFloat(document.getElementById('growth-height').value) : null,
        muac_cm: document.getElementById('growth-muac').value ? parseFloat(document.getElementById('growth-muac').value) : null,
        notes: document.getElementById('growth-notes').value || null
      };

      try {
        const res = await API.recordGrowth(activeGrowthChildId, payload);
        Utils.showToast(`Growth recorded! Nutritional status: ${res.nutritional_status}`, 'success');
        closeGrowthModal();
        growthForm.reset();

        if (activeProfileChildId) await openChildProfileModal(activeProfileChildId);
        await loadAshaDashboard();
        await loadChildrenRoster();
      } catch (err) {
        Utils.showToast(err.message, 'error');
      }
    });
  }

  // 3. Schedule Targeted House Visit Form
  const followUpForm = document.getElementById('followup-note-form');
  if (followUpForm) {
    followUpForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const selectedChildId = parseInt(document.getElementById('followup-child-select').value) || activeFollowUpChildId;
      if (!selectedChildId) {
        Utils.showToast('Please select a child for the visit.', 'error');
        return;
      }

      const reason = document.getElementById('followup-reason-select').value;
      const remarks = document.getElementById('followup-remarks').value || 'Targeted field visit scheduled';
      const visitDate = document.getElementById('followup-date').value;

      const payload = {
        child_id: selectedChildId,
        visit_date: visitDate,
        reason: reason,
        remarks: remarks,
        notes: remarks,
        status: 'scheduled'
      };

      try {
        await API.createHouseVisit(payload);
        Utils.showToast('Targeted house visit scheduled successfully!', 'success');
        closeFollowUpModal();
        followUpForm.reset();

        if (activeProfileChildId) await openChildProfileModal(activeProfileChildId);
        await loadAshaDashboard();
        await loadHouseVisits();
      } catch (err) {
        Utils.showToast(err.message, 'error');
      }
    });
  }

  // 4. Reschedule House Visit Form
  const reschedForm = document.getElementById('reschedule-visit-form');
  if (reschedForm) {
    reschedForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!activeRescheduleVisitId) return;

      const newDate = document.getElementById('resched-new-date').value;
      const reason = document.getElementById('resched-reason').value;

      try {
        await API.rescheduleHouseVisit(activeRescheduleVisitId, newDate, reason);
        Utils.showToast('House visit rescheduled successfully!', 'success');
        closeRescheduleVisitModal();
        reschedForm.reset();
        await loadHouseVisits();
        await loadAshaDashboard();
      } catch (err) {
        Utils.showToast(err.message, 'error');
      }
    });
  }

  // 5. Mark House Visit Completed Form
  const compForm = document.getElementById('complete-visit-form');
  if (compForm) {
    compForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!activeCompleteVisitId) return;

      const remarks = document.getElementById('cv-remarks').value;
      const observations = document.getElementById('cv-observations').value || null;
      const action = document.getElementById('cv-action').value || null;
      const nextDate = document.getElementById('cv-next-date').value || null;

      try {
        await API.completeHouseVisit(activeCompleteVisitId, {
          remarks: remarks,
          observations: observations,
          action_taken: action,
          next_visit_date: nextDate
        });
        Utils.showToast('House visit marked completed! Log saved with timestamp.', 'success');
        closeCompleteVisitModal();
        compForm.reset();
        await loadHouseVisits();
        await loadAshaDashboard();
        if (activeProfileChildId) await openChildProfileModal(activeProfileChildId);
      } catch (err) {
        Utils.showToast(err.message, 'error');
      }
    });
  }

  // 5. Update Permitted Child Fields Form
  const editFieldsForm = document.getElementById('edit-permitted-fields-form');
  if (editFieldsForm) {
    editFieldsForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!activeProfileChildId) return;

      const payload = {
        house_number: document.getElementById('ef-house').value || null,
        parent_contact: document.getElementById('ef-phone').value || null,
        mother_name: document.getElementById('ef-mother').value || null,
        father_name: document.getElementById('ef-father').value || null,
        birth_weight_kg: document.getElementById('ef-weight').value ? parseFloat(document.getElementById('ef-weight').value) : null,
        notes: document.getElementById('ef-notes').value || null
      };

      try {
        await API.updateChild(activeProfileChildId, payload);
        Utils.showToast('Child details updated successfully!', 'success');
        closeEditFieldsModal();
        await openChildProfileModal(activeProfileChildId);
        await loadChildrenRoster();
      } catch (err) {
        Utils.showToast(err.message, 'error');
      }
    });
  }
}
