/**
 * Digital ASHA - Authentication & Authorization Controller
 */

const Auth = {
  /**
   * Initializes page auth guard and enforces role-based client routing
   */
  checkSession(allowedRoles = []) {
    const user = API.getUser();
    const token = API.getToken();

    if (!user || !token) {
      // Not logged in -> redirect to login
      if (!window.location.pathname.endsWith('index.html') && window.location.pathname !== '/') {
        window.location.href = '/index.html?auth_required=1';
      }
      return null;
    }

    if (allowedRoles.length > 0 && !allowedRoles.includes(user.role)) {
      Utils.showToast(`Access restricted for role: ${user.role}`, 'error');
      // Redirect to proper role panel
      if (user.role === 'parent') window.location.href = '/parent.html';
      else if (user.role === 'asha') window.location.href = '/asha.html';
      else if (user.role === 'admin') window.location.href = '/admin.html';
      return null;
    }

    Auth.renderUserBadge(user);
    return user;
  },

  renderUserBadge(user) {
    const nameEl = document.getElementById('nav-user-name');
    const roleEl = document.getElementById('nav-user-role');
    const avatarEl = document.getElementById('nav-user-avatar');

    if (nameEl) nameEl.textContent = user.full_name;
    if (roleEl) {
      const roleLabels = {
        parent: 'Parent Account',
        asha: 'ASHA Field Worker',
        admin: 'Health Administrator'
      };
      roleEl.textContent = roleLabels[user.role] || user.role.toUpperCase();
    }
    if (avatarEl) {
      avatarEl.textContent = user.full_name.charAt(0).toUpperCase();
    }
  },

  async handleLogin(username, password) {
    try {
      const data = await API.login(username, password);
      API.setToken(data.access_token);
      API.setUser({
        id: data.user_id,
        username: data.username,
        full_name: data.full_name,
        role: data.role,
        village_id: data.village_id,
        village_name: data.village_name
      });

      Utils.showToast(`Welcome back, ${data.full_name}!`, 'success');

      // Redirect based on role
      setTimeout(() => {
        if (data.role === 'parent') {
          window.location.href = '/parent.html';
        } else if (data.role === 'asha') {
          window.location.href = '/asha.html';
        } else if (data.role === 'admin') {
          window.location.href = '/admin.html';
        }
      }, 400);
    } catch (err) {
      Utils.showToast(err.message, 'error');
    }
  },

  async handleForgotPassword(usernameOrPhone) {
    try {
      const res = await API.request('/auth/forgot-password', {
        method: 'POST',
        skipAuth: true,
        body: JSON.stringify({ username_or_phone: usernameOrPhone })
      });
      if (res.reset_token) {
        Utils.showToast(`Reset token generated for ${res.username}`, 'info');
        return res.reset_token;
      } else {
        Utils.showToast(res.message, 'info');
        return null;
      }
    } catch (err) {
      Utils.showToast(err.message, 'error');
      throw err;
    }
  },

  async handleResetPassword(token, newPassword) {
    try {
      const res = await API.request('/auth/reset-password', {
        method: 'POST',
        skipAuth: true,
        body: JSON.stringify({ token, new_password: newPassword })
      });
      Utils.showToast(res.message, 'success');
      return true;
    } catch (err) {
      Utils.showToast(err.message, 'error');
      throw err;
    }
  },

  async handleChangePassword(currentPassword, newPassword) {
    try {
      const res = await API.request('/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
      });
      Utils.showToast(res.message, 'success');
      return true;
    } catch (err) {
      Utils.showToast(err.message, 'error');
      throw err;
    }
  },

  logout() {
    API.clearAuth();
    Utils.showToast('Logged out successfully', 'info');
    setTimeout(() => {
      window.location.href = '/index.html';
    }, 300);
  }
};
