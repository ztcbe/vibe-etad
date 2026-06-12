/* ═══════════════════════════════════════════
   api.js — HTTP client wrapper
   ═══════════════════════════════════════════ */

const API_BASE = '/api';

const api = {
  async get(url, params = {}) {
    return this._request('GET', url, null, params);
  },

  async post(url, data = {}) {
    return this._request('POST', url, data);
  },

  async patch(url, data = {}) {
    return this._request('PATCH', url, data);
  },

  async _request(method, url, body, params = {}) {
    const headers = { 'Content-Type': 'application/json' };
    const token = State.get('token');
    if (token) headers['Authorization'] = `Bearer ${token}`;

    let fullUrl = `${API_BASE}${url}`;
    if (Object.keys(params).length) {
      fullUrl += '?' + new URLSearchParams(params);
    }

    const opts = { method, headers };
    if (body && method !== 'GET') opts.body = JSON.stringify(body);

    try {
      const resp = await fetch(fullUrl, opts);
      if (resp.status === 401 && State.get('refreshToken')) {
        // Try refresh
        const refResp = await fetch(`${API_BASE}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: State.get('refreshToken') }),
        });
        if (refResp.ok) {
          const refData = await refResp.json();
          State.set('token', refData.data.access_token);
          State.set('refreshToken', refData.data.refresh_token);
          headers['Authorization'] = `Bearer ${refData.data.access_token}`;
          const retryResp = await fetch(fullUrl, { ...opts, headers });
          return retryResp.json();
        } else {
          State.clear();
          Router.go('auth');
          return { success: false, error: { code: 'UNAUTHORIZED', message: 'Phiên đăng nhập hết hạn' } };
        }
      }
      return resp.json();
    } catch (e) {
      return { success: false, error: { code: 'NETWORK', message: 'Không thể kết nối đến server' } };
    }
  },

  // ── Auth shortcuts ──
  async login(username, password) {
    return this.post('/auth/login', { username, password });
  },
  async register(username, password, confirmPassword, dateOfBirth) {
    return this.post('/auth/register', { username, password, confirm_password: confirmPassword, date_of_birth: dateOfBirth });
  },
  async me() { return this.get('/auth/me'); },
  async logout() {
    const rt = State.get('refreshToken');
    if (rt) await this.post('/auth/logout', { refresh_token: rt });
  },

  // ── Profile shortcuts ──
  async myProfile() { return this.get('/profile/me'); },
  async updateProfile(data) { return this.patch('/profile/me', data); },
  async completeness() { return this.get('/profile/me/completeness'); },
  async publicProfile(userId) { return this.get(`/profile/${userId}`); },

  // ── Matches shortcuts ──
  async searchCandidates(limit = 5) { return this.post('/matches/search', { limit }); },
  async likeCandidate(uid) { return this.post(`/matches/${uid}/like`); },
  async passCandidate(uid) { return this.post(`/matches/${uid}/pass`); },
  async myMatches() { return this.get('/matches'); },

  // ── Chat shortcuts ──
  async chatMessages(matchId, limit = 50) { return this.get(`/chats/${matchId}/messages`, { limit }); },
  async sendMessage(matchId, content) { return this.post(`/chats/${matchId}/messages`, { content }); },
  async suggestReply(matchId, tone = 'natural') { return this.post(`/chats/${matchId}/suggest-reply`, { tone }); },

  // ── Assistant shortcuts ──
  async createSession(title) { return this.post('/assistant/sessions', { title }); },
  async listSessions() { return this.get('/assistant/sessions'); },
  async assistantChat(sessionId, message, context = {}) { return this.post('/assistant/chat', { session_id: sessionId, message, context }); },
  async sessionMessages(sessionId) { return this.get(`/assistant/sessions/${sessionId}/messages`); },

  // ── Admin shortcuts ──
  async adminUsers(page = 1) { return this.get('/admin/users', { page }); },
  async adminReports(page = 1) { return this.get('/admin/reports', { page }); },
  async adminStats() { return this.get('/admin/stats'); },

  // ── Moderation ──
  async reportUser(userId, category, description = '') { return this.post(`/users/${userId}/report`, { category, description }); },
  async blockUser(userId) { return this.post(`/users/${userId}/block`); },
  async unmatch(matchId) { return this.post(`/matches/${matchId}/unmatch`); },
};
