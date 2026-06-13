/* ═══════════════════════════════════════════
   chat.js — 1-1 Chat screen + WebSocket
   ═══════════════════════════════════════════ */

const Chat = {
  _matchId: null,
  _user: null,
  _ws: null,
  _reconnectTimer: null,

  async init(matchId, user) {
    this._matchId = matchId;
    this._user = user;
    State.set('activeChatId', matchId);
    State.set('activeChatUser', user);

    document.getElementById('chat11Name').textContent = `${user.display_name || '...'}, ${user.age || ''}`;
    document.getElementById('chat11Avatar').textContent = user.display_name?.[0] || '👤';
    document.getElementById('chat11Status').textContent = '● đang hoạt động';

    // Load history
    const scroll = document.getElementById('chat11Scroll');
    scroll.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    const resp = await api.chatMessages(matchId);
    scroll.innerHTML = '';
    if (resp.success && resp.data.length > 0) {
      resp.data.forEach(m => this._addMessage(m));
    } else {
      scroll.innerHTML = `<div style="text-align:center;padding:40px;color:var(--ink-soft);font-size:0.88rem">Hãy bắt đầu trò chuyện với ${user.display_name || 'người ấy'}!</div>`;
    }
    scroll.scrollTop = scroll.scrollHeight;

    // Connect WebSocket
    this._connectWs();
  },

  _connectWs() {
    if (this._ws) this._ws.close();
    const token = State.get('token');
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws/chats/${this._matchId}?token=${token}`;

    try {
      this._ws = new WebSocket(wsUrl);
      this._ws.onopen = () => console.log('WS connected');
      this._ws.onmessage = (evt) => {
        const data = JSON.parse(evt.data);
        if (data.event === 'message_created' && data.data.sender_user_id !== State.get('user')?.id) {
          this._addMessage(data.data);
        } else if (data.event === 'match_unavailable') {
          toast('Match này không còn khả dụng', 'error');
          document.getElementById('chat11Input').disabled = true;
          document.getElementById('chat11Status').textContent = '● không khả dụng';
          document.getElementById('chat11Status').style.color = 'var(--danger)';
        } else if (data.event === 'error') {
          toast(data.data.message, 'error');
        }
      };
      this._ws.onclose = () => {
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
    const scroll = document.getElementById('chat11Scroll');
    const isMine = msg.sender_user_id === State.get('user')?.id;
    const row = document.createElement('div');
    row.className = `msg-row${isMine ? ' user' : ''}`;
    const content = marked.parse(msg.content);
    row.innerHTML = `
      <div class="avatar avatar-sm avatar-placeholder" style="background:${isMine ? 'var(--teal-soft)' : 'var(--lavender-soft)'}">${isMine ? '🌿' : (this._user?.display_name?.[0] || '👤')}</div>
      <div class="bubble ${isMine ? 'user' : 'ai'}">${content}</div>
    `;
    scroll.appendChild(row);
    scroll.scrollTop = scroll.scrollHeight;
  },

  async send() {
    const input = document.getElementById('chat11Input');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';

    // Try WS first
    if (this._ws && this._ws.readyState === WebSocket.OPEN) {
      this._ws.send(JSON.stringify({ action: 'send_message', content: text, message_type: 'text' }));
      // Optimistic render
      this._addMessage({ sender_user_id: State.get('user')?.id, content: text });
    } else {
      // REST fallback
      const resp = await api.sendMessage(this._matchId, text);
      if (resp.success) {
        this._addMessage(resp.data);
      } else {
        toast(resp.error?.message || 'Gửi tin nhắn thất bại', 'error');
      }
    }
  },

  async showSuggestions() {
    const tray = document.getElementById('suggestTray');
    if (tray.classList.contains('show')) {
      tray.classList.remove('show');
      return;
    }

    document.getElementById('suggestItems').innerHTML = '<div class="loading" style="padding:8px"><div class="spinner"></div></div>';
    tray.classList.add('show');

    const resp = await api.suggestReply(this._matchId);
    if (resp.success) {
      document.getElementById('suggestItems').innerHTML = resp.data.suggestions.map(s => `
        <div class="suggestion" onclick="Chat._useSuggestion('${s.replace(/'/g, "\\'")}')">${s}</div>
      `).join('');
    }
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
    if (this._ws) { this._ws.close(); this._ws = null; }
    if (this._reconnectTimer) { clearTimeout(this._reconnectTimer); }
  },
};
