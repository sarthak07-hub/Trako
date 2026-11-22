/**
 * TRAKO API Client & Authentication Management
 */

const API_BASE = '/api/v1';

// Toast Notification Manager
function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span>${message}</span>
    <button style="background:transparent;border:none;color:inherit;cursor:pointer;font-weight:bold;" onclick="this.parentElement.remove()">×</button>
  `;
  container.appendChild(toast);

  setTimeout(() => {
    if (toast.parentElement) {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }
  }, 4500);
}

// Core API Fetch Wrapper
async function apiRequest(endpoint, options = {}) {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
  const token = localStorage.getItem('trako_token');

  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers
    });

    if (response.status === 401) {
      // Clear token and redirect if on authenticated page
      const currentPath = window.location.pathname;
      if (!currentPath.includes('login.html') && !currentPath.includes('register.html') && !currentPath.includes('index.html')) {
        localStorage.removeItem('trako_token');
        localStorage.removeItem('trako_user');
        window.location.href = '/pages/login.html';
      }
    }

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      const errorMsg = data && (data.detail || data.message) ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : `Request failed (${response.status})`;
      throw new Error(errorMsg);
    }

    return data;
  } catch (err) {
    console.error(`API Error [${endpoint}]:`, err);
    throw err;
  }
}

// Auth Helpers
function getCurrentUser() {
  const userStr = localStorage.getItem('trako_user');
  if (!userStr) return null;
  try {
    return JSON.parse(userStr);
  } catch (e) {
    return null;
  }
}

function setAuthSession(tokenData) {
  localStorage.setItem('trako_token', tokenData.access_token);
  localStorage.setItem('trako_user', JSON.stringify({
    id: tokenData.user_id,
    email: tokenData.email,
    role: tokenData.role,
    full_name: tokenData.full_name
  }));
}

function logout() {
  localStorage.removeItem('trako_token');
  localStorage.removeItem('trako_user');
  window.location.href = '/pages/login.html';
}

function requireAuth(allowedRoles = []) {
  const user = getCurrentUser();
  const token = localStorage.getItem('trako_token');

  if (!token || !user) {
    window.location.href = `/pages/login.html?redirect=${encodeURIComponent(window.location.pathname)}`;
    return null;
  }

  if (allowedRoles.length > 0 && !allowedRoles.includes(user.role) && user.role !== 'ADMIN') {
    showToast(`Access restricted for ${user.role} role`, 'error');
    // Redirect to respective dashboard
    if (user.role === 'PASSENGER') window.location.href = '/pages/passenger.html';
    else if (user.role === 'OPERATOR') window.location.href = '/pages/operator.html';
    else if (user.role === 'DRIVER') window.location.href = '/pages/driver.html';
    else if (user.role === 'CONDUCTOR') window.location.href = '/pages/conductor.html';
    return null;
  }

  return user;
}

// Navigation Helper
function updateNavUserInfo() {
  const user = getCurrentUser();
  const userSlot = document.getElementById('user-nav-slot');
  if (!userSlot) return;

  if (user) {
    let dashboardLink = '/pages/passenger.html';
    if (user.role === 'OPERATOR') dashboardLink = '/pages/operator.html';
    if (user.role === 'DRIVER') dashboardLink = '/pages/driver.html';
    if (user.role === 'CONDUCTOR') dashboardLink = '/pages/conductor.html';

    userSlot.innerHTML = `
      <div style="display:flex;align-items:center;gap:1rem;">
        <a href="${dashboardLink}" class="btn btn-secondary btn-sm">
          <span>${user.full_name} (${user.role})</span>
        </a>
        <button onclick="logout()" class="btn btn-outline btn-sm">Logout</button>
      </div>
    `;
  } else {
    userSlot.innerHTML = `
      <a href="/pages/login.html" class="btn btn-outline btn-sm">Sign In</a>
      <a href="/pages/register.html" class="btn btn-primary btn-sm">Get Started</a>
    `;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  updateNavUserInfo();
});
