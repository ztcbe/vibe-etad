/* ═══════════════════════════════════════════
   app.js — Global state + router
   ═══════════════════════════════════════════ */

const State = {
  _data: {
    token: null, refreshToken: null,
    user: null, profile: null,
    completeness: 0,
    currentScreen: 'auth',
    matchCount: 0,
    notificationCount: 0,
    activeChatId: null,
    activeChatUser: null,
    assistantSessionId: null,
  },

  get(key) { return this._data[key]; },
  set(key, val) { this._data[key] = val; },
  clear() {
    // Reset all state — prevents cross-user data leakage in SPA
    this._data.token = null;
    this._data.refreshToken = null;
    this._data.user = null;
    this._data.profile = null;
    this._data.completeness = 0;
    this._data.matchCount = 0;
    this._data.notificationCount = 0;
    this._data.activeChatId = null;
    this._data.activeChatUser = null;
    this._data.assistantSessionId = null;
    this._data.currentScreen = 'auth';
  },
};

function iconSvg(name, className = 'ui-icon') {
  return `<svg class="${className}" aria-hidden="true"><use href="#i-${name}"></use></svg>`;
}

function avatarImage(url, alt = 'avatar') {
  return `<img class="avatar-img" src="${url}" alt="${alt}">`;
}

const Router = {
  _current: 'auth',

  go(screen, params = null) {
    // Admin guard — only admin role can access
    if (screen === 'admin') {
      const user = State.get('user');
      if (!user || user.role !== 'admin') {
        toast('Không có quyền truy cập', 'error');
        this.go('home');
        return;
      }
    }

    if (screen === 'auth') {
      // Kill any active WebSocket before hiding
      if (typeof Chat !== 'undefined' && Chat.cleanup) Chat.cleanup();
      Notifications.disconnect();
      document.getElementById('app-shell').style.display = 'none';
      document.getElementById('screen-auth').classList.add('active');
      State.set('currentScreen', 'auth');
      this._current = 'auth';
      this._syncHash('auth');
      // Clean all screen DOMs to prevent old data leaking to next user
      _cleanAllScreens();
      return;
    }

    document.getElementById('screen-auth').classList.remove('active');
    document.getElementById('app-shell').style.display = 'flex';
    State.set('currentScreen', screen);
    this._current = screen;

    // Hide all screens
    ['home', 'matches', 'chat', 'profile', 'admin'].forEach(s => {
      const el = document.getElementById(`screen-${s}`);
      if (el) el.classList.remove('active');
    });

    // Clean chat UI state BEFORE showing new screen (prevents stale data flash)
    if (screen !== 'chat') {
      _resetChatUI();
    }

    // Show target
    const target = document.getElementById(`screen-${screen}`);
    if (target) target.classList.add('active');

    // Update sidebar active state
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    const navRoute = screen === 'chat' ? 'matches' : screen;
    const navItem = document.querySelector(`.nav-item[data-route="${navRoute}"]`);
    if (navItem) navItem.classList.add('active');

    // Adjust app-body for screens without context panel
    const body = document.getElementById('app-body');
    body.classList.remove('no-right', 'no-side');
    if (screen === 'matches' || screen === 'chat' || screen === 'profile' || screen === 'admin') {
      body.classList.add('no-right');
    }

    // Sync URL hash
    this._syncHash(screen, params);

    // Route-specific init
    if (screen === 'home') Assistant.init();
    else if (screen === 'matches') Matches.init();
    else if (screen === 'chat' && params) Chat.init(params.matchId, params.user);
    else if (screen === 'profile') Profile.init();
    else if (screen === 'admin') Admin.init();
  },

  _syncHash(screen, params = null) {
    if (screen === 'auth') {
      history.replaceState(null, '', '/');
      return;
    }
    let hash = `#/${screen}`;
    if (screen === 'chat' && params?.matchId) {
      hash = `#/chat/${params.matchId}`;
    }
    if (location.hash !== hash) {
      history.pushState(null, '', hash);
    }
  },

  init() {
    // Handle browser back/forward
    window.addEventListener('popstate', () => {
      const parsed = this._parseHash();
      if (parsed && State.get('token')) {
        this.go(parsed.screen, parsed.params);
      }
    });

    // Check if logged in
    const token = localStorage.getItem('zvibe_token');
    const refresh = localStorage.getItem('zvibe_refresh');
    if (token && !this._isTokenExpired(token)) {
      State.set('token', token);
      State.set('refreshToken', refresh);
      this.loadUser();
    } else if (token && refresh) {
      // Token expired — try refresh first, don't trigger 401
      State.set('token', token);
      State.set('refreshToken', refresh);
      this._silentRefresh().then(ok => {
        if (ok) this.loadUser();
        else this._clearAndGoAuth();
      });
    } else {
      this.go('auth');
    }
  },

  async loadUser() {
    const resp = await api.me();
    if (resp.success) {
      State.set('user', resp.data);
      State.set('completeness', resp.data.completeness_score || 0);
      this.updateTopbar();
      this._updateAdminNav(resp.data.role);
      // Open global notification WebSocket
      Notifications.connect();
      // Navigate based on URL hash or default to home
      const parsed = this._parseHash();
      if (parsed && parsed.screen !== 'auth') {
        this.go(parsed.screen, parsed.params);
      } else {
        this.go('home');
      }
    } else {
      this._clearAndGoAuth();
    }
  },

  async _silentRefresh() {
    try {
      const rt = State.get('refreshToken');
      if (!rt) return false;
      const resp = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: rt }),
      });
      if (resp.ok) {
        const data = await resp.json();
        State.set('token', data.data.access_token);
        State.set('refreshToken', data.data.refresh_token);
        localStorage.setItem('zvibe_token', data.data.access_token);
        localStorage.setItem('zvibe_refresh', data.data.refresh_token);
        return true;
      }
      return false;
    } catch { return false; }
  },

  _clearAndGoAuth() {
    localStorage.removeItem('zvibe_token');
    localStorage.removeItem('zvibe_refresh');
    Notifications.disconnect();
    State.clear();
    this.go('auth');
  },

  _updateAdminNav(role) {
    let adminNav = document.querySelector('.nav-item[data-route="admin"]');
    if (role === 'admin') {
      if (!adminNav) {
        adminNav = document.createElement('div');
        adminNav.className = 'nav-item';
        adminNav.setAttribute('data-route', 'admin');
        adminNav.onclick = () => Router.go('admin');
        adminNav.innerHTML = `${iconSvg('admin')}<span>Quản trị</span>`;
        const sidebar = document.getElementById('sidebar');
        const divider = sidebar.querySelector('.nav-divider');
        divider.after(adminNav);
      }
    } else {
      if (adminNav) adminNav.remove();
    }
  },

  _parseHash() {
    const hash = location.hash.replace(/^#\/?/, '');
    if (!hash) return null;
    // Pattern: screen/param
    const parts = hash.split('/');
    const screen = parts[0];
    const params = {};
    if (screen === 'chat' && parts[1]) {
      params.matchId = parts[1];
    }
    return { screen, params: Object.keys(params).length ? params : null };
  },

  _isTokenExpired(token) {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      const exp = payload.exp * 1000; // to ms
      return Date.now() >= exp;
    } catch {
      return true; // invalid token → treat as expired
    }
  },

  updateTopbar() {
    const profile = State.get('profile');
    if (profile) {
      document.getElementById('miniName').textContent = `${profile.display_name || '...'}, ${State.get('user')?.date_of_birth ? calcAge(State.get('user').date_of_birth) : ''}`;
      document.getElementById('miniSub').textContent = profile.city || '...';
      // Update mini avatar
      const miniAvatar = document.querySelector('.mini-avatar');
      if (miniAvatar && profile.avatar_url) {
        miniAvatar.innerHTML = avatarImage(profile.avatar_url);
      }
    }
  },
};

function calcAge(dob) {
  const today = new Date();
  const birth = new Date(dob);
  let age = today.getFullYear() - birth.getFullYear();
  if (today.getMonth() < birth.getMonth() || (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate())) age--;
  return age;
}

function _resetChatUI() {
  // Clear suggest tray (prevent stale suggestions from previous match)
  const tray = document.getElementById('suggestTray');
  if (tray) tray.classList.remove('show');
  const items = document.getElementById('suggestItems');
  if (items) items.innerHTML = '';
  // Clear input
  const input = document.getElementById('chat11Input');
  if (input) { input.value = ''; input.disabled = false; }
  // Close menu
  const menu = document.getElementById('chat11Menu');
  if (menu) menu.classList.remove('show');
  // Reset status color
  const status = document.getElementById('chat11Status');
  if (status) status.style.color = '';
}

function _cleanAllScreens() {
  // Clear all screen DOMs when navigating to auth (logout / session switch)
  const homeScroll = document.getElementById('homeChatScroll');
  if (homeScroll) homeScroll.innerHTML = '';
  const chatScroll = document.getElementById('chat11Scroll');
  if (chatScroll) chatScroll.innerHTML = '';
  const matchesList = document.getElementById('matchesList');
  if (matchesList) matchesList.innerHTML = '';
  _resetChatUI();
  const celebration = document.getElementById('celebration');
  if (celebration) celebration.classList.remove('show');
  // Close all modals
  document.querySelectorAll('.overlay.show').forEach(o => o.classList.remove('show'));
  // Clear form fields & errors
  ['authErr', 'regErr'].forEach(id => { const el = document.getElementById(id); if (el) el.textContent = ''; });
  ['loginUser', 'loginPass', 'regUser', 'regPass', 'regPass2'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  // Reset auth form to login view
  document.getElementById('loginForm').style.display = 'block';
  document.getElementById('registerForm').style.display = 'none';
  document.getElementById('authTagline').textContent = 'Hẹn hò có AI đồng hành';
  Auth._isLogin = true;
}

// ── Boot ──
document.addEventListener('DOMContentLoaded', () => Router.init());
