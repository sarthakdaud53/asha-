/**
 * Digital ASHA - Frontend Utilities
 */

const Utils = {
  escapeHtml(value) {
    const text = String(value ?? '');
    return text.replace(/[&<>"']/g, (character) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    }[character]));
  },

  /**
   * Shows toast alert notification
   */
  showToast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    const colors = {
      success: 'bg-emerald-600 text-white',
      error: 'bg-rose-600 text-white',
      warning: 'bg-amber-500 text-white',
      info: 'bg-teal-700 text-white'
    };
    const icons = {
      success: '✓',
      error: '✕',
      warning: '⚠️',
      info: 'ℹ️'
    };

    toast.className = `px-4 py-3 rounded-xl shadow-xl flex items-center space-x-3 text-sm font-medium transition-all transform duration-300 translate-y-2 opacity-0 ${colors[type] || colors.info}`;
    toast.innerHTML = `
      <span class="text-base font-bold">${icons[type] || '•'}</span>
      <span>${Utils.escapeHtml(message)}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.classList.remove('translate-y-2', 'opacity-0');
    }, 10);

    setTimeout(() => {
      toast.classList.add('opacity-0', 'translate-x-4');
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  },

  /**
   * Formats ISO date string to readable format
   */
  formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    });
  },

  /**
   * Generates HTML status badge for vaccines
   */
  getVaccineStatusBadge(status, daysOverdue = 0) {
    const st = (status || '').toLowerCase();
    if (st === 'administered') {
      return `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold badge-administered">
        <span class="w-1.5 h-1.5 mr-1.5 bg-emerald-500 rounded-full"></span> Given / Completed
      </span>`;
    } else if (st === 'overdue') {
      const label = daysOverdue > 0 ? `Overdue (${daysOverdue}d late)` : 'Overdue';
      return `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold badge-overdue">
        <span class="w-1.5 h-1.5 mr-1.5 bg-rose-500 rounded-full animate-ping"></span> ${label}
      </span>`;
    } else if (st === 'due') {
      return `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold badge-due">
        <span class="w-1.5 h-1.5 mr-1.5 bg-amber-500 rounded-full"></span> Due Now
      </span>`;
    } else {
      return `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold badge-upcoming">
        <span class="w-1.5 h-1.5 mr-1.5 bg-slate-400 rounded-full"></span> Upcoming
      </span>`;
    }
  },

  /**
   * Generates HTML status badge for child nutritional status
   */
  getNutritionBadge(status) {
    if (!status) return `<span class="px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-600">Normal</span>`;
    if (status.includes('SAM')) {
      return `<span class="px-2 py-0.5 rounded-full text-xs font-bold badge-sam">SAM - Severe</span>`;
    } else if (status.includes('MAM')) {
      return `<span class="px-2 py-0.5 rounded-full text-xs font-bold badge-mam">MAM - Moderate</span>`;
    } else {
      return `<span class="px-2 py-0.5 rounded-full text-xs font-medium badge-normal">Normal</span>`;
    }
  },

  /**
   * Opens WhatsApp link with pre-filled reminder
   */
  sendWhatsApp(phone, message) {
    if (!phone) {
      Utils.showToast('No phone number available', 'error');
      return;
    }
    // Clean phone number
    let cleanPhone = phone.replace(/[^0-9]/g, '');
    if (cleanPhone.length === 10) cleanPhone = '91' + cleanPhone;
    const url = `https://wa.me/${cleanPhone}?text=${encodeURIComponent(message)}`;
    window.open(url, '_blank');
  },

  /**
   * Prints the MCP card modal
   */
  printMcpCard() {
    window.print();
  }
};
