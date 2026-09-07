/**
 * Digital ASHA - Health Administration Controller
 */

let adminVillages = [];
let ashaWorkers = [];
let allVaccines = [];

document.addEventListener('DOMContentLoaded', async () => {
  const user = Auth.checkSession(['admin']);
  if (!user) return;

  await loadAdminDashboard();
  await loadVillagesTable();
  await loadAshaWorkersList();
  await loadVaccineMasterList();
  await loadUsersTable();
  await loadParentsTable();
  await loadChildrenDirectory();
  await loadVaccinationRecords();
  await loadDistrictReport();
  await loadAuditLogs();
  setupAdminEventListeners();
  setupAdminLocationCascade();
});

async function loadAdminDashboard() {
  try {
    const stats = await API.getAdminDashboard();
    document.getElementById('stat-total-villages').textContent = stats.total_villages;
    document.getElementById('stat-total-ashas').textContent = stats.total_asha_workers;
    document.getElementById('stat-total-children').textContent = stats.total_children;
    document.getElementById('stat-total-administered').textContent = stats.total_vaccines_administered;
    document.getElementById('stat-total-overdue').textContent = stats.total_overdue_cases;
    document.getElementById('stat-overall-rate').textContent = `${stats.overall_immunization_rate}%`;

    // Render Village Coverage Table
    const vTable = document.getElementById('village-coverage-tbody');
    if (vTable && stats.villages_coverage) {
      vTable.innerHTML = stats.villages_coverage.map(v => `
        <tr class="border-b border-slate-100 hover:bg-slate-50 text-sm">
          <td class="py-3 px-4 font-bold text-slate-800">${v.village_name}</td>
          <td class="py-3 px-4 text-slate-600">${v.sub_center}</td>
          <td class="py-3 px-4 text-slate-600">
            <div>${v.asha_name}</div>
            <div class="text-xs text-slate-400 font-mono">${v.asha_phone}</div>
          </td>
          <td class="py-3 px-4 font-semibold text-slate-700">${v.total_children}</td>
          <td class="py-3 px-4 text-emerald-700 font-bold">${v.fully_immunized}</td>
          <td class="py-3 px-4 text-rose-700 font-bold">${v.overdue_cases}</td>
          <td class="py-3 px-4">
            <div class="flex items-center space-x-2">
              <div class="w-16 bg-slate-200 rounded-full h-2">
                <div class="bg-teal-600 h-2 rounded-full" style="width: ${v.coverage_rate}%"></div>
              </div>
              <span class="text-xs font-bold text-slate-800">${v.coverage_rate}%</span>
            </div>
          </td>
        </tr>
      `).join('');
    }
  } catch (err) {
    Utils.showToast(err.message, 'error');
  }
}

async function loadVillagesTable() {
  const tbody = document.getElementById('admin-villages-tbody');
  if (!tbody) return;

  try {
    adminVillages = await API.getAdminVillages();
    tbody.innerHTML = adminVillages.map(v => `
      <tr class="border-b border-slate-100 hover:bg-slate-50 text-sm">
        <td class="py-3 px-4 font-bold text-slate-800">${v.name}</td>
        <td class="py-3 px-4 text-slate-600">${v.sub_center}</td>
        <td class="py-3 px-4 text-slate-600">${v.phc_name}</td>
        <td class="py-3 px-4 text-slate-600">${v.district}, ${v.state}</td>
        <td class="py-3 px-4">
          ${v.asha_worker_name 
            ? `<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-teal-50 text-teal-800 border border-teal-200">👩‍⚕️ ${v.asha_worker_name}</span>`
            : `<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200">⚠️ Unassigned</span>`
          }
        </td>
        <td class="py-3 px-4 font-semibold text-slate-700">${v.total_children}</td>
        <td class="py-3 px-4 text-right">
          <button 
            onclick="openAssignAshaModal(${v.id}, '${v.name.replace(/'/g, "\\'")}')" 
            class="px-2.5 py-1.5 rounded-lg text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300">
            Assign ASHA
          </button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load admin villages', err);
  }
}

async function loadAshaWorkersList() {
  try {
    ashaWorkers = await API.getAshaWorkers();
    const select = document.getElementById('assign-asha-select');
    if (select) {
      select.innerHTML = '<option value="">-- Select ASHA Worker --</option>' +
        ashaWorkers.map(a => `<option value="${a.id}">${a.full_name} (${a.phone})</option>`).join('');
    }
  } catch (err) {
    console.error('Failed to load ASHA workers', err);
  }
}

async function loadVaccineMasterList() {
  const tbody = document.getElementById('admin-vaccines-tbody');
  if (!tbody) return;

  try {
    allVaccines = await API.getVaccines();
    tbody.innerHTML = allVaccines.map(v => `
      <tr class="border-b border-slate-100 hover:bg-slate-50 text-sm">
        <td class="py-3 px-4 font-mono font-bold text-teal-800">${v.code}</td>
        <td class="py-3 px-4 font-bold text-slate-800">${v.name}</td>
        <td class="py-3 px-4 text-slate-600">${v.category}</td>
        <td class="py-3 px-4 text-slate-600">${v.target_age_label} (${v.target_age_days}d)</td>
        <td class="py-3 px-4 text-slate-600">${v.dose_amount} • ${v.route}</td>
        <td class="py-3 px-4 text-xs text-slate-500 max-w-xs truncate" title="${v.prevents_diseases}">${v.prevents_diseases}</td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load vaccines', err);
  }
}

// ----------------- Assign ASHA Modal -----------------
let activeAssignVillageId = null;
function openAssignAshaModal(villageId, villageName) {
  activeAssignVillageId = villageId;
  const modal = document.getElementById('assign-asha-modal');
  modal.classList.remove('hidden');
  document.getElementById('assign-village-name').textContent = villageName;
}

function closeAssignAshaModal() {
  document.getElementById('assign-asha-modal').classList.add('hidden');
}

// ----------------- Create Village Modal -----------------
function openCreateVillageModal() {
  document.getElementById('create-village-modal').classList.remove('hidden');
}

function closeCreateVillageModal() {
  document.getElementById('create-village-modal').classList.add('hidden');
}

// ----------------- Section 3: User Management -----------------
async function loadUsersTable() {
  const tbody = document.getElementById('admin-users-tbody');
  if (!tbody) return;
  try {
    const roleFilter = document.getElementById('users-role-filter')?.value || '';
    const users = await API.getAdminUsers(roleFilter ? { role: roleFilter } : {});
    tbody.innerHTML = users.map(u => `
      <tr class="border-b border-slate-100 hover:bg-slate-50 text-sm">
        <td class="py-3 px-4 font-bold text-slate-800">${u.full_name}</td>
        <td class="py-3 px-4 text-slate-600">${u.username} <span class="text-slate-400 font-mono text-xs">${u.phone}</span></td>
        <td class="py-3 px-4"><span class="px-2 py-0.5 rounded-lg text-xs font-bold bg-slate-100 text-slate-700 capitalize">${u.role}</span></td>
        <td class="py-3 px-4">
          ${u.is_active
            ? `<span class="px-2 py-0.5 rounded-lg text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">Active</span>`
            : `<span class="px-2 py-0.5 rounded-lg text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200">Inactive</span>`}
        </td>
        <td class="py-3 px-4 text-right space-x-2">
          <button onclick="toggleUserStatus(${u.id}, ${!u.is_active})" class="px-2.5 py-1.5 rounded-lg text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300">
            ${u.is_active ? 'Deactivate' : 'Activate'}
          </button>
          <button onclick="adminResetUserPassword(${u.id}, '${u.username}')" class="px-2.5 py-1.5 rounded-lg text-xs font-bold bg-sky-50 hover:bg-sky-100 text-sky-700 border border-sky-200">
            Reset Password
          </button>
          <button onclick="openSendNotificationModal(${u.id}, '${u.full_name}')" class="px-2.5 py-1.5 rounded-lg text-xs font-bold bg-violet-50 hover:bg-violet-100 text-violet-700 border border-violet-200">
            Notify
          </button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load users', err);
  }
}

async function toggleUserStatus(userId, newStatus) {
  try {
    await API.toggleUserStatus(userId, newStatus);
    Utils.showToast(`User ${newStatus ? 'activated' : 'deactivated'} successfully.`, 'success');
    await loadUsersTable();
  } catch (err) {
    Utils.showToast(err.message, 'error');
  }
}

async function adminResetUserPassword(userId, username) {
  const newPassword = prompt(`Enter a new temporary password for ${username} (min 6 characters):`);
  if (!newPassword) return;
  if (newPassword.length < 6) {
    Utils.showToast('Password must be at least 6 characters.', 'warning');
    return;
  }
  try {
    await API.adminResetPassword(userId, newPassword);
    Utils.showToast(`Password reset for ${username}.`, 'success');
  } catch (err) {
    Utils.showToast(err.message, 'error');
  }
}

// ----------------- Section 4: Parents Directory -----------------
async function loadParentsTable() {
  const tbody = document.getElementById('admin-parents-tbody');
  if (!tbody) return;
  try {
    const parents = await API.getAdminParents();
    tbody.innerHTML = parents.map(p => `
      <tr class="border-b border-slate-100 hover:bg-slate-50 text-sm">
        <td class="py-3 px-4 font-bold text-slate-800">${p.full_name}</td>
        <td class="py-3 px-4 text-slate-600 font-mono">${p.phone}</td>
        <td class="py-3 px-4 text-slate-600">${p.occupation || '—'}</td>
        <td class="py-3 px-4 text-slate-700">${p.total_families}</td>
        <td class="py-3 px-4 font-semibold text-slate-700">${p.total_children}</td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load parents', err);
  }
}

// ----------------- Section 5: Children Directory -----------------
async function loadChildrenDirectory() {
  const tbody = document.getElementById('admin-children-tbody');
  if (!tbody) return;
  try {
    const status = document.getElementById('children-verification-filter')?.value || '';
    const children = await API.getAdminChildren(status ? { verification_status: status } : {});
    tbody.innerHTML = children.map(c => `
      <tr class="border-b border-slate-100 hover:bg-slate-50 text-sm">
        <td class="py-3 px-4 font-bold text-slate-800">${c.full_name}</td>
        <td class="py-3 px-4 text-slate-600">${c.village_name}</td>
        <td class="py-3 px-4 text-slate-600">${c.parent_name} <span class="text-slate-400 font-mono text-xs">${c.parent_phone}</span></td>
        <td class="py-3 px-4">
          ${c.verification_status === 'verified'
            ? `<span class="px-2 py-0.5 rounded-lg text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">Verified</span>`
            : `<span class="px-2 py-0.5 rounded-lg text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">Pending</span>`}
        </td>
        <td class="py-3 px-4 text-slate-700">${c.completed_vaccines}/${c.total_vaccines} <span class="text-xs text-slate-400">(${c.immunization_rate}%)</span></td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load children directory', err);
  }
}

// ----------------- Section 6: Vaccination Records -----------------
async function loadVaccinationRecords() {
  const tbody = document.getElementById('admin-vaccination-records-tbody');
  if (!tbody) return;
  try {
    const status = document.getElementById('vaccination-status-filter')?.value || '';
    const records = await API.getAdminVaccinationRecords(status ? { record_status: status } : {});
    tbody.innerHTML = records.map(r => `
      <tr class="border-b border-slate-100 hover:bg-slate-50 text-sm">
        <td class="py-3 px-4 font-bold text-slate-800">${r.child_name}</td>
        <td class="py-3 px-4 text-slate-600">${r.village_name}</td>
        <td class="py-3 px-4 text-slate-600">${r.vaccine_name}</td>
        <td class="py-3 px-4 text-slate-600">${r.scheduled_date || '—'}</td>
        <td class="py-3 px-4 text-slate-600">${r.administered_date || '—'}</td>
        <td class="py-3 px-4 text-slate-500 text-xs">${r.administered_by_name || '—'}</td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load vaccination records', err);
  }
}

// ----------------- Section 7: District Reports -----------------
async function loadDistrictReport() {
  const cardsDiv = document.getElementById('report-summary-cards');
  const tbody = document.getElementById('admin-report-tbody');
  if (!cardsDiv || !tbody) return;
  try {
    const report = await API.getAdminReport();
    document.getElementById('report-generated-on').textContent = `Generated on ${report.generated_on}`;

    cardsDiv.innerHTML = `
      <div class="p-4 bg-slate-50 rounded-2xl text-center">
        <span class="text-xs font-bold text-slate-500 uppercase block">Total Children</span>
        <span class="text-2xl font-black text-slate-800">${report.total_children}</span>
      </div>
      <div class="p-4 bg-emerald-50 rounded-2xl text-center">
        <span class="text-xs font-bold text-emerald-700 uppercase block">Fully Immunized</span>
        <span class="text-2xl font-black text-emerald-800">${report.fully_immunized}</span>
      </div>
      <div class="p-4 bg-amber-50 rounded-2xl text-center">
        <span class="text-xs font-bold text-amber-700 uppercase block">Partially Immunized</span>
        <span class="text-2xl font-black text-amber-800">${report.partially_immunized}</span>
      </div>
      <div class="p-4 bg-rose-50 rounded-2xl text-center">
        <span class="text-xs font-bold text-rose-700 uppercase block">Overdue Cases</span>
        <span class="text-2xl font-black text-rose-800">${report.total_overdue}</span>
      </div>
    `;

    tbody.innerHTML = report.per_village.map(v => `
      <tr class="border-b border-slate-100 hover:bg-slate-50 text-sm">
        <td class="py-3 px-4 font-bold text-slate-800">${v.village_name}</td>
        <td class="py-3 px-4 text-slate-700">${v.total_children}</td>
        <td class="py-3 px-4 text-emerald-700 font-bold">${v.fully_immunized}</td>
        <td class="py-3 px-4 text-amber-700 font-bold">${v.partially_immunized}</td>
        <td class="py-3 px-4 text-rose-700 font-bold">${v.overdue_cases}</td>
        <td class="py-3 px-4 font-semibold text-slate-800">${v.coverage_rate}%</td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load district report', err);
  }
}

// ----------------- Section 8: Audit Logs -----------------
async function loadAuditLogs() {
  const tbody = document.getElementById('admin-audit-tbody');
  if (!tbody) return;
  try {
    const logs = await API.getAdminAuditLogs(50);
    tbody.innerHTML = logs.map(l => `
      <tr class="border-b border-slate-100 hover:bg-slate-50 text-xs">
        <td class="py-3 px-4 text-slate-500 whitespace-nowrap">${new Date(l.created_at).toLocaleString()}</td>
        <td class="py-3 px-4 font-semibold text-slate-700">${l.username}</td>
        <td class="py-3 px-4"><span class="px-2 py-0.5 rounded-lg font-bold bg-slate-100 text-slate-700">${l.action}</span></td>
        <td class="py-3 px-4 text-slate-500">${l.entity_type}${l.entity_id ? ' #' + l.entity_id : ''}</td>
        <td class="py-3 px-4 text-slate-500 max-w-sm truncate" title="${l.details || ''}">${l.details || '—'}</td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load audit logs', err);
  }
}

function setupAdminEventListeners() {
  // Create village form
  const vForm = document.getElementById('create-village-form');
  if (vForm) {
    vForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        name: document.getElementById('new-village-name').value,
        sub_center: document.getElementById('new-village-subcenter').value,
        phc_name: document.getElementById('new-village-phc').value,
        district: document.getElementById('new-village-district').value,
        state: 'Madhya Pradesh',
        location_village_id: parseInt(document.getElementById('new-village-location').value),
        pin_code: document.getElementById('new-village-pincode').value || null
      };

      try {
        await API.createVillage(payload);
        Utils.showToast('Village created successfully!', 'success');
        closeCreateVillageModal();
        vForm.reset();
        await loadAdminDashboard();
        await loadVillagesTable();
      } catch (err) {
        Utils.showToast(err.message, 'error');
      }

    });
  }

  // Assign ASHA form
  const assignForm = document.getElementById('assign-asha-form');
  if (assignForm) {
    assignForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const ashaId = document.getElementById('assign-asha-select').value;
      if (!ashaId || !activeAssignVillageId) {
        Utils.showToast('Please select an ASHA worker', 'warning');
        return;
      }

      try {
        await API.assignAshaToVillage(activeAssignVillageId, parseInt(ashaId));
        Utils.showToast('ASHA worker assigned successfully!', 'success');
        closeAssignAshaModal();
        await loadAdminDashboard();
        await loadVillagesTable();
      } catch (err) {
        Utils.showToast(err.message, 'error');
      }
    });
  }
}

async function setupAdminLocationCascade() {
  const state = document.getElementById('new-village-state');
  const district = document.getElementById('new-village-district-select');
  const taluka = document.getElementById('new-village-taluka');
  const village = document.getElementById('new-village-location');
  if (!state) return;
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
    const rows = taluka.value ? await API.getLocationVillages(taluka.value) : [];
    fill(village, '-- Choose village --', rows);
    if (rows.length) document.getElementById('new-village-name').value = rows[0].name;
  });
}
