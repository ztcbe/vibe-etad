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
    activeChatId: null,
    activeChatUser: null,
    assistantSessionId: null,
  },

  get(key) { return this._data[key]; },
  set(key, val) { this._data[key] = val; },
  clear() {
    this._data.token = null;
    this._data.refreshToken = null;
    this._data.user = null;
    this._data.profile = null;
  },
};

const Router = {
  _current: 'auth',

  go(screen, params = null) {
    if (screen === 'auth') {
      document.getElementById('app-shell').style.display = 'none';
      document.getElementById('screen-auth').classList.add('active');
      State.set('currentScreen', 'auth');
      this._current = 'auth';
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

    // Show target
    const target = document.getElementById(`screen-${screen}`);
    if (target) target.classList.add('active');

    // Update sidebar active state
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    const navItem = document.querySelector(`.nav-item[data-route="${screen}"]`);
    if (navItem) navItem.classList.add('active');

    // Adjust app-body for screens without context panel
    const body = document.getElementById('app-body');
    body.classList.remove('no-right', 'no-side');
    if (screen === 'matches' || screen === 'chat' || screen === 'profile' || screen === 'admin') {
      body.classList.add('no-right');
    }

    // Route-specific init
    if (screen === 'home') Assistant.init();
    else if (screen === 'matches') Matches.init();
    else if (screen === 'chat' && params) Chat.init(params.matchId, params.user);
    else if (screen === 'profile') Profile.init();
    else if (screen === 'admin') Admin.init();
  },

  init() {
    // Check if logged in
    const token = localStorage.getItem('zvibe_token');
    const refresh = localStorage.getItem('zvibe_refresh');
    if (token) {
      State.set('token', token);
      State.set('refreshToken', refresh);
      this.loadUser();
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
      this.go('home');
    } else {
      localStorage.removeItem('zvibe_token');
      localStorage.removeItem('zvibe_refresh');
      State.clear();
      this.go('auth');
    }
  },

  updateTopbar() {
    const comp = State.get('completeness');
    document.getElementById('compLabel').textContent = comp;
    document.getElementById('compBar').style.width = comp + '%';

    const profile = State.get('profile');
    if (profile) {
      document.getElementById('miniName').textContent = `${profile.display_name || '...'}, ${State.get('user')?.date_of_birth ? calcAge(State.get('user').date_of_birth) : ''}`;
      document.getElementById('miniSub').textContent = profile.city || '...';
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

// ── Boot ──
document.addEventListener('DOMContentLoaded', () => Router.init());
