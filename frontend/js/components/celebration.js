/* ═══════════════════════════════════════════
   celebration.js — Match celebration overlay
   ═══════════════════════════════════════════ */

const Celebration = {
  _matchId: null,
  _user: null,

  show(matchId, user) {
    this._matchId = matchId;
    this._user = user;
    document.getElementById('celebTitle').textContent = `Match rồi! Bạn và ${user?.display_name || 'người ấy'} đã thích nhau`;
    document.getElementById('celebMsg').textContent = 'Cả hai có thể bắt đầu trò chuyện ngay bây giờ.';
    document.getElementById('celebration').classList.add('show');
  },

  goToChat() {
    document.getElementById('celebration').classList.remove('show');
    if (this._matchId && this._user) {
      Router.go('chat', { matchId: this._matchId, user: this._user });
    }
  },
};
