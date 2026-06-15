/* ═══════════════════════════════════════════
   assistant.js — AI Assistant (Home) screen
   ═══════════════════════════════════════════ */

const Assistant = {
  _sessionId: null,
  _loading: false,

  async init() {
    // Clear previous state — prevents old chat from showing after logout/register
    this._sessionId = null;
    document.getElementById('homeChatScroll').innerHTML = '';

    // Load profile for context panel
    const prof = await api.myProfile();
    if (prof.success) {
      State.set('profile', prof.data);
      State.set('completeness', prof.data.completeness_score || 0);
      Router.updateTopbar();
      document.getElementById('ctxVibe').textContent = prof.data.public_summary || prof.data.bio || 'Hoàn thiện hồ sơ để hiển thị vibe của bạn';
      const tags = document.getElementById('ctxTags');
      const hobbies = prof.data.hobbies;
      if (hobbies && Array.isArray(hobbies)) {
        tags.innerHTML = hobbies.slice(0, 5).map(h => `<span class="tag">${h}</span>`).join('');
      } else if (hobbies && typeof hobbies === 'object') {
        tags.innerHTML = Object.keys(hobbies).slice(0, 5).map(h => `<span class="tag">${h}</span>`).join('');
      }
    }

    // Get or create assistant session
    const sessions = await api.listSessions();
    if (sessions.success && sessions.data.length > 0) {
      this._sessionId = sessions.data[0].id;
      // Load existing messages
      await this._loadHistory();
    } else {
      const s = await api.createSession('Trợ lý hẹn hò');
      if (s.success) this._sessionId = s.data.id;
    }

    // Store session ID in global state for notifications
    State.set('assistantSessionId', this._sessionId);

    // Mark both assistant messages AND notifications as read, then clear badge
    if (this._sessionId) {
      await api.markAssistantRead(this._sessionId);
      await api.markNotificationsRead();
      Notifications._updateBadge(0);
    }

    // Show welcome if no messages
    const scroll = document.getElementById('homeChatScroll');
    if (!scroll.querySelector('.msg-row')) {
      this._addBubble('ai', 'Chào bạn. Mình là trợ lý của zvibe. Mình có thể giúp bạn tạo hồ sơ, tìm người hợp vibe, xem danh sách match và tư vấn cách bắt đầu trò chuyện. Bạn muốn làm gì hôm nay?');
    }
  },

  async _loadHistory() {
    const resp = await api.sessionMessages(this._sessionId);
    if (resp.success) {
      const scroll = document.getElementById('homeChatScroll');
      scroll.innerHTML = '';
      resp.data.forEach(m => {
        this._addBubble(m.role === 'user' ? 'user' : 'ai', m.content);
      });
      scroll.scrollTop = scroll.scrollHeight;
    }
  },

  async send() {
    if (this._loading) return;
    const input = document.getElementById('homeChatInput');
    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    this._addBubble('user', text);

    // Show typing
    this._loading = true;
    const typingEl = this._addTyping();

    const resp = await api.assistantChat(this._sessionId, text);
    this._loading = false;
    typingEl?.remove();

    if (resp.success) {
      this._addBubble('ai', resp.data.message);
      // Render candidate cards if present
      if (resp.data.actions) {
        resp.data.actions.forEach(action => {
          if (action.type === 'candidate_cards' && action.payload?.cards) {
            action.payload.cards.forEach(card => this._addCandidateCard(card));
          }
          if (action.type === 'profile_summary_card') {
            // Profile was updated — refresh profile data + UI immediately
            api.myProfile().then(p => {
              if (p.success) {
                State.set('profile', p.data);
                State.set('completeness', p.data.completeness_score || 0);
                Router.updateTopbar();
                _updateAllAvatars(p.data.avatar_url);
              }
            });
          }
        });
      }
    } else {
      this._addBubble('ai', resp.error?.message || 'Có lỗi xảy ra, bạn thử lại nhé!');
    }
  },

  _addBubble(role, text) {
    const scroll = document.getElementById('homeChatScroll');
    const row = document.createElement('div');
    row.className = `msg-row${role === 'user' ? ' user' : ''}`;
    const content = role === 'user' ? escapeHtml(text) : marked.parse(text);
    // Show actual avatar image if available, else fallback icon.
    let userAvatar = iconSvg('user', 'ui-icon avatar-symbol');
    const profile = State.get('profile');
    if (role === 'user' && profile?.avatar_url) {
      userAvatar = avatarImage(profile.avatar_url);
    }
    row.innerHTML = `
      <div class="avatar avatar-sm avatar-placeholder ${role === 'user' ? 'user-av' : 'ai'}">${role === 'user' ? userAvatar : iconSvg('spark', 'ui-icon avatar-symbol')}</div>
      <div class="bubble ${role}">${content}</div>
    `;
    scroll.appendChild(row);
    scroll.scrollTop = scroll.scrollHeight;
    return row;
  },

  _addTyping() {
    const scroll = document.getElementById('homeChatScroll');
    const row = document.createElement('div');
    row.className = 'msg-row';
    row.id = 'typingIndicator';
    row.innerHTML = `
      <div class="avatar avatar-sm avatar-placeholder">${iconSvg('spark', 'ui-icon avatar-symbol')}</div>
      <div class="bubble ai"><div class="typing-dots"><span></span><span></span><span></span></div></div>
    `;
    scroll.appendChild(row);
    scroll.scrollTop = scroll.scrollHeight;
    return row;
  },

  _addCandidateCard(card) {
    const scroll = document.getElementById('homeChatScroll');
    const tierClass = card.score_tier || 'medium';
    const reasonTexts = card.reasons?.join('<br>') || '';
    const considerTexts = card.considerations?.join('<br>') || '';
    const goalLabel = { serious: 'Tìm người nghiêm túc', casual: 'Tìm bạn', friends_first: 'Tìm hiểu', not_sure: 'Chưa rõ' };
    const row = document.createElement('div');
    row.className = 'msg-row';
    row.innerHTML = `
      <div class="avatar avatar-sm avatar-placeholder">${iconSvg('spark', 'ui-icon avatar-symbol')}</div>
      <div class="candidate-card">
        <div class="candidate-head">
          <div class="avatar avatar-md avatar-placeholder">${card.display_name?.[0] || '?'}</div>
          <div class="candidate-info"><div class="name">${card.display_name}, ${card.age}</div><div class="meta">${card.city || ''} · ${goalLabel[card.dating_goal] || card.dating_goal || ''}</div></div>
          <div class="score-badge ${tierClass}">${card.score}%</div>
        </div>
        <div class="candidate-body">
          <div class="reason"><span class="lbl">Hợp:</span> ${reasonTexts}</div>
          <div class="consider"><span class="lbl">Cân nhắc:</span> ${considerTexts || 'Không có điểm đáng lưu ý'}</div>
        </div>
        <div class="candidate-actions">
          <button onclick="Assistant._action('pass','${card.candidate_user_id}')">Bỏ qua</button>
          <button onclick="Assistant._action('ask','${card.candidate_user_id}')">Hỏi thêm</button>
          <button class="primary" onclick="Assistant._action('like','${card.candidate_user_id}','${card.display_name}')">Thích</button>
        </div>
      </div>
    `;
    scroll.appendChild(row);
    scroll.scrollTop = scroll.scrollHeight;
  },

  async _action(type, uid, name = '') {
    if (type === 'like') {
      const resp = await api.likeCandidate(uid);
      if (resp.success && resp.data.is_mutual) {
        Celebration.show(resp.data.match_id, resp.data.user);
      } else if (resp.success) {
        toast(`Đã gửi lời thích đến ${name || 'người này'}`, 'success');
      } else {
        toast(resp.error?.message || 'Lỗi', 'error');
      }
    } else if (type === 'pass') {
      await api.passCandidate(uid);
      toast('Đã bỏ qua', 'info');
    } else if (type === 'ask') {
      const input = document.getElementById('homeChatInput');
      input.value = `Kể mình thêm về người này đi`;
      Assistant.send();
    }
  },

  async _handleUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Show image preview in chat as user bubble
    const imageUrl = URL.createObjectURL(file);
    this._addImageBubble('user', imageUrl, file.name);

    // Show typing
    this._loading = true;
    const typingEl = this._addTyping();

    const resp = await api.uploadAvatar(file);
    this._loading = false;
    typingEl?.remove();

    if (resp.success) {
      const avatarUrl = resp.data.url;
      // Update all avatar displays immediately
      _updateAllAvatars(avatarUrl);

      // Update profile state
      const prof = State.get('profile') || {};
      prof.avatar_url = avatarUrl;
      State.set('profile', prof);

      // Show success in chat
      this._addBubble('ai', 'Ảnh đại diện của bạn đã được cập nhật. Bạn có thể xem ở phần Hồ sơ.');

      // Also update profile screen if visible
      const profAvatar = document.getElementById('profileAvatar');
      if (profAvatar) {
        profAvatar.innerHTML = avatarImage(avatarUrl);
      }
    } else {
      this._addBubble('ai', 'Không thể tải ảnh lên: ' + (resp.error?.message || 'Lỗi không xác định'));
    }

    // Reset file input
    event.target.value = '';

    // Revoke object URL after a short delay (ensure browser has time to render)
    setTimeout(() => URL.revokeObjectURL(imageUrl), 5000);
  },

  _addImageBubble(role, src, alt = 'image') {
    const scroll = document.getElementById('homeChatScroll');
    const row = document.createElement('div');
    row.className = `msg-row${role === 'user' ? ' user' : ''}`;
    let avatarHtml = iconSvg('user', 'ui-icon avatar-symbol');
    const profile = State.get('profile');
    if (role === 'user' && profile?.avatar_url) {
      avatarHtml = avatarImage(profile.avatar_url);
    }
    row.innerHTML = `
      <div class="avatar avatar-sm avatar-placeholder ${role === 'user' ? 'user-av' : 'ai'}">${role === 'user' ? avatarHtml : iconSvg('spark', 'ui-icon avatar-symbol')}</div>
      <div class="bubble ${role}"><img src="${src}" alt="${escapeHtml(alt)}" style="max-width:240px;max-height:320px;border-radius:12px;cursor:pointer" onclick="window.open(this.src)"></div>
    `;
    scroll.appendChild(row);
    scroll.scrollTop = scroll.scrollHeight;
    return row;
  },

  quickFind() {
    document.getElementById('homeChatInput').value = 'Tìm cho mình người hợp vibe đi';
    this.send();
  },
};

function _updateAllAvatars(url) {
  if (!url) return;
  const imgTag = avatarImage(url);

  // Update mini-avatar in sidebar
  const miniAvatar = document.querySelector('.mini-avatar');
  if (miniAvatar) miniAvatar.innerHTML = imgTag;

  // Update profile screen avatar
  const profAvatar = document.getElementById('profileAvatar');
  if (profAvatar) profAvatar.innerHTML = imgTag;

  // Update all user message avatars in assistant chat
  document.querySelectorAll('#homeChatScroll .msg-row.user .avatar.user-av').forEach(el => {
    el.innerHTML = imgTag;
  });

  // Update all user message avatars in 1-1 chat
  document.querySelectorAll('#chat11Scroll .msg-row.user .avatar').forEach(el => {
    el.innerHTML = imgTag;
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>');
}
