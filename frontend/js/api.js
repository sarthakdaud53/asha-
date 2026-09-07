/**
 * Digital ASHA - Centralized API Service Layer
 */

const API_BASE = '/api';

const API = {
  formatErrorDetail(detail) {
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => {
        if (typeof item === 'string') return item;
        const location = Array.isArray(item.loc) ? item.loc.join('.') : '';
        const message = item.msg || item.message || JSON.stringify(item);
        return location ? `${location}: ${message}` : message;
      }).join('; ');
    }
    if (detail && typeof detail === 'object') {
      return detail.message || detail.msg || JSON.stringify(detail);
    }
    return 'An unexpected error occurred.';
  },

  getToken() {
    return sessionStorage.getItem('digital_asha_token');
  },

  setToken(token) {
    sessionStorage.setItem('digital_asha_token', token);
  },

  getUser() {
    const raw = localStorage.getItem('digital_asha_user');
    return raw ? JSON.parse(raw) : null;
  },

  setUser(user) {
    localStorage.setItem('digital_asha_user', JSON.stringify(user));
  },

  clearAuth() {
    sessionStorage.removeItem('digital_asha_token');
    localStorage.removeItem('digital_asha_user');
  },

  async request(endpoint, options = {}) {
    const { skipAuth = false, ...requestOptions } = options;
    const token = API.getToken();
    const headers = {
      'Content-Type': 'application/json',
      ...(requestOptions.headers || {})
    };

    if (token && !skipAuth) {
            headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        ...requestOptions,
        headers
      });

      if (response.status === 401 && token && !skipAuth) {
        // Token expired or invalid
        API.clearAuth();
        if (!window.location.pathname.endsWith('index.html') && window.location.pathname !== '/') {
          window.location.href = '/index.html?session_expired=1';
        }
        throw new Error('Session expired. Please log in again.');
      }

      if (response.status === 204) {
        return null;
      }

      const data = await response.json();

      if (!response.ok) {
        throw new Error(API.formatErrorDetail(data.detail));
      }

      return data;
    } catch (err) {
      console.error(`API Error [${endpoint}]:`, err);
      throw err;
    }
  },

  // Auth Endpoints
  async login(username, password) {
    return API.request('/auth/login', {
      method: 'POST',
      skipAuth: true,
      body: JSON.stringify({ username, password })
    });
  },

  async register(userData) {
    return API.request('/auth/register', {
      method: 'POST',
      skipAuth: true,
      body: JSON.stringify(userData)
    });
  },

  async submitAshaApplication(application) {
    return API.request('/auth/asha-applications', {
      method: 'POST',
      skipAuth: true,
      body: JSON.stringify(application)
    });
  },

  async getMe() {
    return API.request('/auth/me');
  },

  async getVillages() {
    return API.request('/auth/villages', { skipAuth: true });
  },

  async getLocationStates() {
    return API.request('/locations/states', { skipAuth: true });
  },

  async getLocationDistricts(stateId) {
    return API.request(`/locations/districts?state_id=${stateId}`, { skipAuth: true });
  },

  async getLocationTalukas(districtId) {
    return API.request(`/locations/talukas?district_id=${districtId}`, { skipAuth: true });
  },

  async getLocationVillages(talukaId, search = '') {
    const params = new URLSearchParams({ taluka_id: talukaId, search, limit: '100' });
    return API.request(`/locations/villages?${params}`, { skipAuth: true });
  },

  // Children Endpoints
  async getChildren(params = {}) {
    const q = new URLSearchParams(params).toString();
    return API.request(`/children?${q}`);
  },

  async getChildDetail(childId) {
    return API.request(`/children/${childId}`);
  },

  async registerChild(childData) {
    return API.request('/children', {
      method: 'POST',
      body: JSON.stringify(childData)
    });
  },

  async updateChild(childId, childData) {
    return API.request(`/children/${childId}`, {
      method: 'PUT',
      body: JSON.stringify(childData)
    });
  },

  async verifyChild(childId) {
    return API.request(`/children/${childId}/verify`, {
      method: 'POST'
    });
  },

  async deleteChild(childId) {
    return API.request(`/children/${childId}`, {
      method: 'DELETE'
    });
  },

  // Immunization Endpoints
  async administerVaccine(recordId, administerData) {
    return API.request(`/immunizations/${recordId}/administer`, {
      method: 'POST',
      body: JSON.stringify(administerData)
    });
  },

  async getMcpCardData(childId) {
    return API.request(`/immunizations/mcp-card/${childId}`);
  },

  // Growth Endpoints
  async recordGrowth(childId, growthData) {
    return API.request(`/growth/${childId}`, {
      method: 'POST',
      body: JSON.stringify(growthData)
    });
  },

  async getGrowthHistory(childId) {
    return API.request(`/growth/child/${childId}`);
  },

  // ASHA Operations Endpoints
  async getAshaDashboard() {
    return API.request('/asha/dashboard');
  },

  async getPriorityFollowUps(priority = '') {
    const q = priority ? `?priority=${priority}` : '';
    return API.request(`/asha/priority-follow-ups${q}`);
  },

  async getAshaFamilies() {
    return API.request('/asha/families');
  },

  async getAshaHouseVisits(params = {}) {
    const q = typeof params === 'string' ? `?category=${params}` : `?${new URLSearchParams(params).toString()}`;
    return API.request(`/asha/house-visits${q}`);
  },

  async getAshaHouseVisitCounts() {
    return API.request('/asha/house-visits/counts');
  },

  async createHouseVisit(visitData) {
    return API.request('/asha/house-visits', {
      method: 'POST',
      body: JSON.stringify(visitData)
    });
  },

  async rescheduleHouseVisit(visitId, newDate, reason = '') {
    const q = new URLSearchParams({ new_visit_date: newDate, reason: reason }).toString();
    return API.request(`/asha/house-visits/${visitId}/reschedule?${q}`, {
      method: 'PUT'
    });
  },

  async completeHouseVisit(visitId, params = {}) {
    const q = new URLSearchParams(params).toString();
    return API.request(`/asha/house-visits/${visitId}/complete?${q}`, {
      method: 'PUT'
    });
  },

  async generateSmartVisitPlan() {
    return API.request('/asha/house-visits/smart-plan', {
      method: 'POST'
    });
  },

  async getAshaReports() {
    return API.request('/asha/reports');
  },

  async getFollowUpPlanner(filterType = 'all') {
    return API.request(`/asha/follow-ups?filter_type=${filterType}`);
  },

  async logFollowUpNote(noteData) {
    return API.request('/asha/follow-up-notes', {
      method: 'POST',
      body: JSON.stringify(noteData)
    });
  },

  // Notification Center Endpoints
  async getNotifications(params = {}) {
    const q = new URLSearchParams(params).toString();
    return API.request(`/notifications${q ? '?' + q : ''}`);
  },

  async getUnreadNotificationCount() {
    return API.request('/notifications/unread-count');
  },

  async markNotificationRead(notifId) {
    return API.request(`/notifications/${notifId}/read`, {
      method: 'POST'
    });
  },

  async markAllNotificationsRead() {
    return API.request('/notifications/read-all', {
      method: 'POST'
    });
  },

  async triggerAutoNotifications() {
    return API.request('/notifications/trigger-auto-generation', {
      method: 'POST'
    });
  },

  async sendCustomNotification(payload) {
    return API.request('/notifications', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  // Admin Endpoints
  async getAdminDashboard() {
    return API.request('/admin/dashboard');
  },

  async getAdminVillages() {
    return API.request('/admin/villages');
  },

  async createVillage(villageData) {
    return API.request('/admin/villages', {
      method: 'POST',
      body: JSON.stringify(villageData)
    });
  },

  async assignAshaToVillage(villageId, ashaId) {
    return API.request(`/admin/villages/${villageId}/assign-asha?asha_id=${ashaId}`, {
      method: 'PUT'
    });
  },

  async getAshaWorkers() {
    return API.request('/admin/asha-workers');
  },

  // Admin Extended Endpoints
  async getAdminUsers(params = {}) {
    const q = new URLSearchParams(params).toString();
    return API.request(`/admin/users${q ? '?' + q : ''}`);
  },

  async getAdminParents() {
    return API.request('/admin/parents');
  },

  async getAdminChildren(params = {}) {
    const q = new URLSearchParams(params).toString();
    return API.request(`/admin/children${q ? '?' + q : ''}`);
  },

  async getAdminVaccinationRecords(params = {}) {
    const q = new URLSearchParams(params).toString();
    return API.request(`/admin/vaccination-records${q ? '?' + q : ''}`);
  },

  async getAdminReport() {
    return API.request('/admin/reports/summary');
  },

  async toggleUserStatus(userId, isActive) {
    return API.request(`/admin/users/${userId}/status?is_active=${isActive}`, {
      method: 'PUT'
    });
  },

  async adminResetPassword(userId, newPassword) {
    return API.request(`/admin/users/${userId}/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ new_password: newPassword })
    });
  },

  // Vaccine Schedule CRUD (admin)
  async getVaccines(includeInactive = false) {
    return API.request(`/vaccines${includeInactive ? '?include_inactive=true' : ''}`);
  },

  async createVaccine(vaccineData) {
    return API.request('/vaccines', {
      method: 'POST',
      body: JSON.stringify(vaccineData)
    });
  },

  async updateVaccine(vaccineId, vaccineData) {
    return API.request(`/vaccines/${vaccineId}`, {
      method: 'PUT',
      body: JSON.stringify(vaccineData)
    });
  },

  async deactivateVaccine(vaccineId) {
    return API.request(`/vaccines/${vaccineId}/deactivate`, { method: 'PUT' });
  },

  async activateVaccine(vaccineId) {
    return API.request(`/vaccines/${vaccineId}/activate`, { method: 'PUT' });
  },

  async provisionAshaWorker(ashaData) {
    return API.request('/admin/asha-workers', {
      method: 'POST',
      body: JSON.stringify(ashaData)
    });
  },

  async getAdminAuditLogs(limit = 100) {
    return API.request(`/admin/audit-logs?limit=${limit}`);
  },
};
