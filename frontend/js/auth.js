/* ═══════════════════════════════════════════
   auth.js — Login + Register (username/password)
   ═══════════════════════════════════════════ */

const Auth = {
  _isLogin: true,

  toggleForm() {
    this._isLogin = !this._isLogin;
    document.getElementById('loginForm').style.display = this._isLogin ? 'block' : 'none';
    document.getElementById('registerForm').style.display = this._isLogin ? 'none' : 'block';
    document.getElementById('authTagline').textContent = this._isLogin ? 'Hẹn hò có AI đồng hành' : 'Tạo tài khoản mới';
  },

  async login() {
    const username = document.getElementById('loginUser').value.trim();
    const password = document.getElementById('loginPass').value;
    const errEl = document.getElementById('authErr');

    if (!username || !password) { errEl.textContent = 'Vui lòng nhập username và mật khẩu'; return; }

    errEl.textContent = '';
    const btn = document.querySelector('#loginForm .btn');
    btn.innerHTML = '<span class="spinner"></span> Đang đăng nhập...';
    btn.disabled = true;

    const resp = await api.login(username, password);
    btn.innerHTML = 'Đăng nhập';
    btn.disabled = false;

    if (resp.success) {
      // Clear any previous user state before setting new tokens
      State.clear();
      State.set('token', resp.data.access_token);
      State.set('refreshToken', resp.data.refresh_token);
      localStorage.setItem('zvibe_token', resp.data.access_token);
      localStorage.setItem('zvibe_refresh', resp.data.refresh_token);
      await Router.loadUser();
    } else {
      errEl.textContent = resp.error?.message || 'Đăng nhập thất bại';
    }
  },

  async register() {
    const username = document.getElementById('regUser').value.trim();
    const pass = document.getElementById('regPass').value;
    const pass2 = document.getElementById('regPass2').value;
    const dob = document.getElementById('regDob').value;
    const errEl = document.getElementById('regErr');

    if (!username || !pass || !dob) { errEl.textContent = 'Vui lòng điền đầy đủ thông tin'; return; }
    if (username.length < 3) { errEl.textContent = 'Username tối thiểu 3 ký tự'; return; }
    if (pass !== pass2) { errEl.textContent = 'Mật khẩu không khớp'; return; }
    if (pass.length < 8) { errEl.textContent = 'Mật khẩu tối thiểu 8 ký tự'; return; }

    errEl.textContent = '';
    const btn = document.querySelector('#registerForm .btn');
    btn.innerHTML = '<span class="spinner"></span> Đang tạo tài khoản...';
    btn.disabled = true;

    const resp = await api.register(username, pass, pass2, dob);
    btn.innerHTML = 'Đăng ký';
    btn.disabled = false;

    if (resp.success) {
      // Clear any previous user state before setting new tokens
      State.clear();
      State.set('token', resp.data.access_token);
      State.set('refreshToken', resp.data.refresh_token);
      localStorage.setItem('zvibe_token', resp.data.access_token);
      localStorage.setItem('zvibe_refresh', resp.data.refresh_token);
      toast('Đăng ký thành công! Hãy hoàn thiện hồ sơ để trợ lý tìm người hợp vibe cho bạn.', 'success');
      await Router.loadUser();
    } else {
      errEl.textContent = resp.error?.message || 'Đăng ký thất bại';
    }
  },

  async logout() {
    await api.logout();
    localStorage.removeItem('zvibe_token');
    localStorage.removeItem('zvibe_refresh');
    State.clear();
    // Kill any active WebSocket
    if (typeof Chat !== 'undefined' && Chat.cleanup) Chat.cleanup();
    Router.go('auth');
    toast('Đã đăng xuất', 'info');
  },
};
