/* ═══════════════════════════════════════════
   profile.js — My Profile screen
   ═══════════════════════════════════════════ */

const Profile = {
  async init() {
    document.getElementById('profileName').textContent = '...';
    document.getElementById('profileBio').textContent = 'Đang tải...';
    document.getElementById('profileTags').innerHTML = '';

    const resp = await api.myProfile();
    if (!resp.success) {
      document.getElementById('profileBio').textContent = 'Không thể tải hồ sơ';
      return;
    }

    const p = resp.data;
    State.set('profile', p);
    const age = State.get('user')?.date_of_birth ? calcAge(State.get('user').date_of_birth) : '';

    // Show actual avatar or fallback
    const avatarEl = document.getElementById('profileAvatar');
    if (p.avatar_url) {
      avatarEl.innerHTML = `<img src="${p.avatar_url}" alt="avatar" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`;
    } else {
      avatarEl.textContent = '🌿';
    }

    document.getElementById('profileName').textContent = `${p.display_name || 'Chưa đặt tên'}, ${age}`;
    document.getElementById('profileCity').textContent = p.city || 'Chưa có thành phố';
    document.getElementById('profileBio').textContent = p.bio || p.public_summary || 'Chưa có giới thiệu. Hãy nói chuyện với trợ lý để cập nhật!';

    // Visibility pill
    const vis = p.visibility_status;
    const visEl = document.getElementById('profileVisibility');
    visEl.className = `visibility-pill${vis === 'paused' ? ' paused' : vis === 'hidden' ? ' hidden' : ' active'}`;
    const visLabels = { active: '● Đang hiển thị (Active)', paused: '⏸ Tạm ẩn (Paused)', hidden: '🔒 Đã ẩn (Hidden)' };
    visEl.textContent = visLabels[vis] || vis;

    // Tags: hobbies + personality traits
    const tags = document.getElementById('profileTags');
    const allTags = [];
    if (p.hobbies) {
      if (Array.isArray(p.hobbies)) allTags.push(...p.hobbies);
      else if (typeof p.hobbies === 'object') allTags.push(...Object.keys(p.hobbies));
    }
    if (p.personality_traits) {
      if (Array.isArray(p.personality_traits)) allTags.push(...p.personality_traits);
      else if (typeof p.personality_traits === 'object') allTags.push(...Object.keys(p.personality_traits));
    }
    tags.innerHTML = allTags.length > 0 ? allTags.map(t => `<span class="tag">${t}</span>`).join('') : '<span style="color:var(--ink-faint);font-size:0.82rem">Chưa có — cập nhật qua trợ lý</span>';

    // Dating goal
    const goalLabels = { serious: 'Tìm một mối quan hệ nghiêm túc, hướng tới gắn bó lâu dài.', casual: 'Tìm bạn, gặp gỡ nhẹ nhàng, không áp lực.', friends_first: 'Làm bạn trước, tìm hiểu từ từ.', not_sure: 'Đang khám phá, chưa xác định rõ mục tiêu.' };
    document.getElementById('profileGoal').textContent = goalLabels[p.dating_goal] || 'Chưa xác định mục tiêu hẹn hò';

    Router.updateTopbar();
  },
};

// Admin screen
const Admin = {
  async init() {
    const stats = await api.adminStats();
    if (stats.success) {
      document.getElementById('adminStats').innerHTML = `
        <div class="stat-card"><div class="num">${stats.data.total_users}</div><div class="label">Tổng users</div></div>
        <div class="stat-card"><div class="num">${stats.data.active_users}</div><div class="label">Đang hoạt động</div></div>
        <div class="stat-card"><div class="num">${stats.data.total_matches}</div><div class="label">Matches</div></div>
        <div class="stat-card"><div class="num">${stats.data.open_reports}</div><div class="label">Reports mở</div></div>
      `;
    }

    const usersResp = await api.adminUsers(1);
    if (usersResp.success) {
      document.getElementById('adminUserTable').innerHTML = usersResp.data.items.map(u => `
        <tr><td>${u.username}</td><td>${u.display_name || '-'}</td><td>${u.role}</td><td><span class="status-pill ${u.status}">${u.status}</span></td><td>${u.date_of_birth}</td><td>${u.completeness_score}%</td></tr>
      `).join('');
    }
  },
};
