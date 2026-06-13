/* ═══════════════════════════════════════════
   assistant.js — AI Assistant (Home) screen
   ═══════════════════════════════════════════ */

const Assistant = {
  _sessionId: null,
  _loading: false,

  async init() {
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

    // Show welcome if no messages
    const scroll = document.getElementById('homeChatScroll');
    if (!scroll.querySelector('.msg-row')) {
      this._addBubble('ai', 'Chào bạn! Mình là trợ lý của zvibe 👋 Mình có thể giúp bạn tạo hồ sơ, tìm người hợp vibe, xem danh sách match, và tư vấn cho bạn. Bạn muốn làm gì hôm nay?');
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
    row.innerHTML = `
      <div class="avatar avatar-sm avatar-placeholder ${role === 'user' ? 'user-av' : 'ai'}" style="background:${role === 'user' ? 'var(--teal-soft)' : 'var(--lavender-soft)'}">${role === 'user' ? '🌿' : '🤍'}</div>
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
      <div class="avatar avatar-sm avatar-placeholder" style="background:var(--lavender-soft)">🤍</div>
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
      <div class="avatar avatar-sm avatar-placeholder" style="background:var(--lavender-soft)">🤍</div>
      <div class="candidate-card">
        <div class="candidate-head">
          <div class="avatar avatar-md avatar-placeholder" style="background:var(--teal-soft)">${card.display_name?.[0] || '👤'}</div>
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
          <button class="primary" onclick="Assistant._action('like','${card.candidate_user_id}','${card.display_name}')">💖 Thích</button>
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
        toast(`Đã gửi lời thích đến ${name || 'người này'}!`, 'success');
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

  quickFind() {
    document.getElementById('homeChatInput').value = 'Tìm cho mình người hợp vibe đi';
    this.send();
  },
};

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>');
}
