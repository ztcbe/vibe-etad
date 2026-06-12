/* ═══════════════════════════════════════════
   modal.js — Unmatch / Report / Block modals
   ═══════════════════════════════════════════ */

const Modal = {
  _currentType: null,

  show(type) {
    this._currentType = type;
    document.getElementById(`overlay${type.charAt(0).toUpperCase() + type.slice(1)}`).classList.add('show');
  },

  hide(type) {
    document.getElementById(`overlay${type.charAt(0).toUpperCase() + type.slice(1)}`).classList.remove('show');
    this._currentType = null;
  },

  async confirm(type) {
    const matchId = State.get('activeChatId');
    const userId = State.get('activeChatUser')?.user_id;

    if (type === 'unmatch') {
      const resp = await api.unmatch(matchId);
      if (resp.success) {
        toast('Đã unmatch', 'info');
        this.hide('unmatch');
        Router.go('matches');
      } else {
        toast(resp.error?.message || 'Lỗi', 'error');
      }
    } else if (type === 'report') {
      const category = document.querySelector('input[name="rpt"]:checked')?.value || 'harassment';
      const resp = await api.reportUser(userId, category);
      if (resp.success) {
        toast('Đã gửi báo cáo', 'success');
        this.hide('report');
      } else {
        toast(resp.error?.message || 'Lỗi', 'error');
      }
    } else if (type === 'block') {
      const resp = await api.blockUser(userId);
      if (resp.success) {
        toast('Đã block người này', 'info');
        this.hide('block');
        Router.go('matches');
      } else {
        toast(resp.error?.message || 'Lỗi', 'error');
      }
    }
  },
};
