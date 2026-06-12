/* ═══════════════════════════════════════════
   matches.js — Matches list screen
   ═══════════════════════════════════════════ */

const Matches = {
  async init() {
    const container = document.getElementById('matchesList');
    container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    const resp = await api.myMatches();
    if (!resp.success) {
      container.innerHTML = '<div class="empty-state"><div class="icon">🌱</div><h3>Chưa có match nào</h3><p>Hãy nói chuyện với trợ lý để tìm người hợp vibe!</p></div>';
      return;
    }

    const { matched, pending_sent } = resp.data;
    container.innerHTML = '';

    // Matched group
    if (matched.length > 0) {
      const title = document.createElement('div');
      title.className = 'matches-group-title';
      title.textContent = '💞 Đã match — có thể chat ngay';
      container.appendChild(title);

      matched.forEach(m => {
        const item = document.createElement('div');
        item.className = 'match-item';
        item.onclick = () => Router.go('chat', { matchId: m.match_id, user: m.user });
        const preview = m.last_message ? m.last_message.content : 'Chưa có tin nhắn — bắt đầu chat?';
        const unread = m.unread_count > 0 ? '<div class="unread-dot"></div>' : '';
        const time = m.matched_at ? timeAgo(m.matched_at) : '';
        item.innerHTML = `
          <div class="avatar match-avatar avatar-placeholder" style="background:var(--gold-soft)">${m.user.display_name?.[0] || '👤'}</div>
          <div class="match-text"><div class="name">${m.user.display_name || '...'}, ${m.user.age || ''}</div><div class="preview">${preview}</div></div>
          <div class="match-meta">${time}${unread}</div>
        `;
        container.appendChild(item);
      });
    }

    // Pending group
    if (pending_sent.length > 0) {
      const title = document.createElement('div');
      title.className = 'matches-group-title';
      title.textContent = '⏳ Đã thích, đang chờ phản hồi';
      container.appendChild(title);

      pending_sent.forEach(p => {
        const item = document.createElement('div');
        item.className = 'match-item';
        item.innerHTML = `
          <div class="avatar match-avatar avatar-placeholder" style="background:var(--sage-soft)">${p.user.display_name?.[0] || '👤'}</div>
          <div class="match-text"><div class="name">${p.user.display_name || '...'}, ${p.user.age || ''}</div><div class="preview">Bạn đã thích — đang chờ phản hồi</div></div>
          <div class="match-meta">${timeAgo(p.liked_at)}</div>
        `;
        container.appendChild(item);
      });
    }

    if (matched.length === 0 && pending_sent.length === 0) {
      container.innerHTML = '<div class="empty-state"><div class="icon">🌱</div><h3>Chưa có match nào</h3><p>Hãy nói chuyện với trợ lý: "Tìm người hợp vibe đi!"</p></div>';
    }

    // Update badge
    const count = matched.reduce((sum, m) => sum + (m.unread_count || 0), 0);
    State.set('matchCount', count);
    const badge = document.getElementById('matchBadge');
    if (badge) {
      badge.textContent = count;
      badge.style.display = count > 0 ? 'inline' : 'none';
    }
    if (document.getElementById('matchBadge2')) {
      document.getElementById('matchBadge2').textContent = count;
    }
  },
};

function timeAgo(dateStr) {
  const now = new Date();
  const then = new Date(dateStr);
  const diff = Math.floor((now - then) / 1000);
  if (diff < 60) return 'vừa xong';
  if (diff < 3600) return Math.floor(diff / 60) + ' phút trước';
  if (diff < 86400) return Math.floor(diff / 3600) + ' giờ trước';
  if (diff < 604800) return Math.floor(diff / 86400) + ' ngày trước';
  return Math.floor(diff / 604800) + ' tuần trước';
}
