/* ═══════════════════════════════════════════
   notifications.js — Global notification WebSocket + badge
   ═══════════════════════════════════════════ */

const Notifications = {
  _ws: null,
  _reconnectTimer: null,

  connect() {
    const token = State.get('token');
    if (!token) return;

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${location.host}/ws/notifications?token=${encodeURIComponent(token)}`;

    this._ws = new WebSocket(url);

    this._ws.onopen = () => {
      console.log('Notification WS connected');
      if (this._reconnectTimer) {
        clearTimeout(this._reconnectTimer);
        this._reconnectTimer = null;
      }
      // Fetch initial unread count on connect
      this.fetchUnreadCount();
    };

    this._ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this._handleEvent(data);
      } catch (e) {
        // ignore parse errors
      }
    };

    this._ws.onclose = (ev) => {
      if (ev.code === 4001) {
        // Auth error — token expired, don't reconnect
        return;
      }
      // Reconnect after 3 seconds
      if (!this._reconnectTimer) {
        this._reconnectTimer = setTimeout(() => this.connect(), 3000);
      }
    };

    this._ws.onerror = () => {
      this._ws.close();
    };
  },

  disconnect() {
    if (this._ws) {
      this._ws.close();
      this._ws = null;
    }
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
  },

  async fetchUnreadCount() {
    const resp = await api.unreadCount();
    if (resp.success && resp.data) {
      this._updateBadge(resp.data.total || 0);
    }
  },

  _handleEvent(data) {
    if (data.event === 'notification') {
      const d = data.data;
      toast(d.title + (d.body ? ': ' + d.body : ''), 'info');
      const current = parseInt(document.getElementById('assistantBadge')?.textContent || '0');
      this._updateBadge(current + 1);
    } else if (data.event === 'assistant_message') {
      const content = data.data.content || 'Có thông báo mới từ trợ lý';
      toast(content, 'info');
      const current = parseInt(document.getElementById('assistantBadge')?.textContent || '0');
      this._updateBadge(current + 1);

      // Append to assistant chat in real-time if user is on home screen
      if (State.get('currentScreen') === 'home' && typeof Assistant !== 'undefined') {
        Assistant._addBubble('ai', content);
      }
    } else if (data.event === 'unread_message') {
      // New chat message from a match — update match badge, not assistant badge
      const d = data.data;
      toast(`Tin nhắn mới từ ${d.sender_name}`, 'info');
      this._updateMatchBadge();
    } else if (data.event === 'pong') {
      // heartbeat response — ignore
    }
  },

  _updateMatchBadge() {
    const count = (State.get('matchCount') || 0) + 1;
    State.set('matchCount', count);
    const badge = document.getElementById('matchBadge');
    if (badge) {
      badge.textContent = count > 99 ? '99+' : count;
      badge.style.display = count > 0 ? 'inline' : 'none';
    }
  },

  _updateBadge(count) {
    count = Math.max(0, count || 0);
    State.set('notificationCount', count);

    const badge = document.getElementById('assistantBadge');
    if (badge) {
      badge.textContent = count > 99 ? '99+' : count;
      badge.style.display = count > 0 ? 'inline' : 'none';
    }
  },

  async clearBadge() {
    // Called when user opens assistant chat
    const sessionId = State.get('assistantSessionId');
    if (sessionId) {
      await api.markAssistantRead(sessionId);
    }
    // Also mark notification read
    await api.markNotificationsRead();
    this._updateBadge(0);
  },
};
