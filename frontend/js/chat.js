/* ═══════════════════════════════════════════
   chat.js — 1-1 Chat screen + WebSocket
   ═══════════════════════════════════════════ */

const Chat = {
  _matchId: null,
  _user: null,
  _isBot: false,
  _ws: null,
  _wsGen: 0,           // generation counter — detects stale WS connections
  _reconnectTimer: null,
  _sending: false,      // guard against double-send
  _renderedIds: new Set(),  // dedup rendered message IDs
  _typingEl: null,      // bot typing indicator element

  async init(matchId, user) {
    // Clean up previous chat state before initializing new one
    this.cleanup();
    this._matchId = matchId;
    this._user = user;
    this._renderedIds = new Set();
    State.set('activeChatId', matchId);
    State.set('activeChatUser', user);

    document.getElementById('chat11Name').textContent = `${user.display_name || '...'}, ${user.age || ''}`;
    document.getElementById('chat11Avatar').textContent = user.display_name?.[0] || '?';
    this._isBot = user.is_bot || false;
    const isOnline = user.is_online !== undefined ? user.is_online : true;
    const statusEl = document.getElementById('chat11Status');
    statusEl.textContent = isOnline ? 'đang hoạt động' : 'không hoạt động';
    statusEl.style.color = isOnline ? 'var(--teal)' : 'var(--ink-soft)';

    // Load history
    const scroll = document.getElementById('chat11Scroll');
    scroll.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    const resp = await api.chatMessages(matchId);
    scroll.innerHTML = '';
    if (resp.success && resp.data.length > 0) {
      resp.data.forEach(m => this._addMessage(m));
    } else {
      scroll.innerHTML = `<div class="empty-state"><div class="icon">${iconSvg('chat')}</div><h3>Bắt đầu cuộc trò chuyện</h3><p>Gửi lời chào đầu tiên tới ${user.display_name || 'người ấy'}.</p></div>`;
    }
    scroll.scrollTop = scroll.scrollHeight;

    // Connect WebSocket
    this._connectWs();
  },

  _connectWs() {
    // Kill any existing connection and pending reconnect
    if (this._ws) {
      this._ws.onclose = null;  // prevent stale onclose from firing
      this._ws.close();
      this._ws = null;
    }
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }

    const token = State.get('token');
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws/chats/${this._matchId}?token=${token}`;

    const gen = ++this._wsGen;  // capture generation for THIS connection

    try {
      this._ws = new WebSocket(wsUrl);
      this._ws.onopen = () => console.log('WS connected gen', gen);
      this._ws.onmessage = (evt) => {
        const data = JSON.parse(evt.data);
        if (data.event === 'message_created' && data.data.sender_user_id !== State.get('user')?.id) {
          this._removeTyping();
          this._addMessage(data.data);
          // Auto mark as read since chat is open (use current WS, not stale ref)
          const currentWs = this._ws;
          if (currentWs && currentWs.readyState === WebSocket.OPEN) {
            currentWs.send(JSON.stringify({ action: 'mark_read', message_ids: [data.data.id] }));
          }
        } else if (data.event === 'match_unavailable') {
          toast('Match này không còn khả dụng', 'error');
          document.getElementById('chat11Input').disabled = true;
          document.getElementById('chat11Status').textContent = 'không khả dụng';
          document.getElementById('chat11Status').style.color = 'var(--danger)';
        } else if (data.event === 'error') {
          toast(data.data.message, 'error');
        }
      };
      this._ws.onclose = () => {
        // Only act if this is still the current generation
        if (this._wsGen !== gen) return;
        this._ws = null;
        // Reconnect after 3s
        this._reconnectTimer = setTimeout(() => this._connectWs(), 3000);
      };
      this._ws.onerror = () => { /* will trigger onclose */ };
    } catch (e) {
      console.log('WS failed, using REST fallback');
    }
  },

  _addMessage(msg) {
    // Dedup by message ID — skip if already rendered
    if (msg.id) {
      if (this._renderedIds.has(msg.id)) return;
      this._renderedIds.add(msg.id);
    }
    const scroll = document.getElementById('chat11Scroll');
    const isMine = msg.sender_user_id === State.get('user')?.id;
    const row = document.createElement('div');
    row.className = `msg-row${isMine ? ' user' : ''}`;
    const content = marked.parse(msg.content);
    // Show actual avatar image if available.
    let myAvatar = iconSvg('user', 'ui-icon avatar-symbol');
    if (isMine) {
      const profile = State.get('profile');
      if (profile?.avatar_url) {
        myAvatar = avatarImage(profile.avatar_url);
      } else {
        myAvatar = iconSvg('user', 'ui-icon avatar-symbol');
      }
    }
    row.innerHTML = `
      <div class="avatar avatar-sm avatar-placeholder">${isMine ? myAvatar : (this._user?.display_name?.[0] || '?')}</div>
      <div class="bubble ${isMine ? 'user' : 'ai'}">${content}</div>
    `;
    scroll.appendChild(row);
    scroll.scrollTop = scroll.scrollHeight;
  },

  _addTyping() {
    if (this._typingEl) return;
    const scroll = document.getElementById('chat11Scroll');
    const row = document.createElement('div');
    row.className = 'msg-row';
    row.id = 'chat11Typing';
    row.innerHTML = `
      <div class="avatar avatar-sm avatar-placeholder">${this._user?.display_name?.[0] || '?'}</div>
      <div class="bubble ai"><div class="typing-dots"><span></span><span></span><span></span></div></div>
    `;
    scroll.appendChild(row);
    scroll.scrollTop = scroll.scrollHeight;
    this._typingEl = row;
  },

  _removeTyping() {
    if (this._typingEl) {
      this._typingEl.remove();
      this._typingEl = null;
    }
  },

  async send() {
    // Guard against rapid double-sends
    if (this._sending) return;
    const input = document.getElementById('chat11Input');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    this._sending = true;

    try {
      // Try WS first
      if (this._ws && this._ws.readyState === WebSocket.OPEN) {
        this._ws.send(JSON.stringify({ action: 'send_message', content: text, message_type: 'text' }));
        // Optimistic render
        this._addMessage({ sender_user_id: State.get('user')?.id, content: text });
        // Show typing for bot matches
        if (this._isBot) this._addTyping();
      } else {
        // REST fallback
        const resp = await api.sendMessage(this._matchId, text);
        if (resp.success) {
          this._addMessage(resp.data);
        } else {
          toast(resp.error?.message || 'Gửi tin nhắn thất bại', 'error');
        }
      }
    } finally {
      this._sending = false;
    }
  },

  async showSuggestions() {
    const tray = document.getElementById('suggestTray');
    if (tray.classList.contains('show')) {
      tray.classList.remove('show');
      return;
    }

    const itemsEl = document.getElementById('suggestItems');
    itemsEl.innerHTML = '<div class="loading loading-tight"><div class="spinner"></div></div>';
    tray.classList.add('show');

    const resp = await api.suggestReply(this._matchId);
    if (resp.success) {
      itemsEl.innerHTML = resp.data.suggestions.map((s, i) => `
        <div class="suggestion" data-text="${s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}">${s}</div>
      `).join('');
    }

    // Event delegation — single handler on container, no inline onclick
    itemsEl.onclick = (e) => {
      const el = e.target.closest('.suggestion');
      if (!el) return;
      const text = el.getAttribute('data-text');
      if (text) this._useSuggestion(text);
    };
  },

  _useSuggestion(text) {
    document.getElementById('chat11Input').value = text;
    document.getElementById('suggestTray').classList.remove('show');
    document.getElementById('chat11Input').focus();
  },

  toggleMenu(e) {
    e.stopPropagation();
    const menu = document.getElementById('chat11Menu');
    menu.classList.toggle('show');
    // Close on outside click
    if (menu.classList.contains('show')) {
      const close = (ev) => { menu.classList.remove('show'); document.removeEventListener('click', close); };
      setTimeout(() => document.addEventListener('click', close), 0);
    }
  },

  cleanup() {
    // ── WS cleanup ──
    if (this._ws) {
      this._ws.onclose = null;  // prevent stale onclose
      this._ws.close();
      this._ws = null;
    }
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    this._wsGen++;  // invalidate all previous generations
    this._sending = false;

    // ── UI cleanup — prevent stale state leaking across matches ──
    const tray = document.getElementById('suggestTray');
    if (tray) tray.classList.remove('show');
    const suggestItems = document.getElementById('suggestItems');
    if (suggestItems) suggestItems.innerHTML = '';

    const input = document.getElementById('chat11Input');
    if (input) { input.value = ''; input.disabled = false; }

    const menu = document.getElementById('chat11Menu');
    if (menu) menu.classList.remove('show');

    const statusEl = document.getElementById('chat11Status');
    if (statusEl) statusEl.style.color = '';
  },
};
