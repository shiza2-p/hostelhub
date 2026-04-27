/**
 * api.js  –  HostelHub central API client
 * All pages import this file via <script src="../js/api.js">
 */

const API = (() => {

  // ── Base URL: same origin as Flask server ──────────────────
  const BASE = '/api';

  // ── Token helpers ──────────────────────────────────────────
  function getToken()          { return localStorage.getItem('hh_token'); }
  function setToken(t)         { localStorage.setItem('hh_token', t); }
  function clearToken()        { localStorage.removeItem('hh_token'); localStorage.removeItem('hh_user'); }
  function getUser()           { try { return JSON.parse(localStorage.getItem('hh_user') || 'null'); } catch { return null; } }
  function setUser(u)          { localStorage.setItem('hh_user', JSON.stringify(u)); }
  function isLoggedIn()        { return !!getToken(); }
  function isAdmin()           { const u = getUser(); return u && u.role === 'admin'; }

  // ── Core fetch wrapper ─────────────────────────────────────
  async function req(method, path, body = null, auth = false) {
    const headers = { 'Content-Type': 'application/json' };
    if (auth) {
      const token = getToken();
      if (!token) { redirectToLogin(); return null; }
      headers['Authorization'] = 'Bearer ' + token;
    }
    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);

    try {
      const res  = await fetch(BASE + path, opts);
      const data = await res.json();
      return { ok: res.ok, status: res.status, data };
    } catch (err) {
      return { ok: false, status: 0, data: { message: 'Network error. Is the server running?' } };
    }
  }

  // ── Redirect helpers ───────────────────────────────────────
  function redirectToLogin()     { window.location.href = '/pages/login.html'; }
  function redirectToDashboard() { window.location.href = '/pages/dashboard.html'; }

  /** Guard: call at top of protected pages */
  function requireLogin() {
    if (!isLoggedIn()) { redirectToLogin(); }
  }

  /** Guard: redirect logged-in users away from login/signup */
  function redirectIfLoggedIn() {
    if (isLoggedIn()) { redirectToDashboard(); }
  }

  // ── Toast notification ─────────────────────────────────────
  function toast(message, type = 'success') {
    const existing = document.getElementById('hh-toast');
    if (existing) existing.remove();

    const colors = { success: '#0d7a4e', error: '#c0392b', info: '#1a3c5e', warning: '#c25a00' };
    const div = document.createElement('div');
    div.id = 'hh-toast';
    div.style.cssText = `
      position:fixed;bottom:24px;right:24px;z-index:9999;
      background:${colors[type] || colors.info};color:white;
      padding:12px 20px;border-radius:8px;font-size:.9rem;
      box-shadow:0 4px 16px rgba(0,0,0,.25);max-width:320px;
      animation:slideIn .3s ease;
    `;
    div.textContent = message;

    const style = document.createElement('style');
    style.textContent = '@keyframes slideIn{from{transform:translateX(110%)}to{transform:translateX(0)}}';
    document.head.appendChild(style);

    document.body.appendChild(div);
    setTimeout(() => div.remove(), 4000);
  }

  // ── Auth ───────────────────────────────────────────────────
  async function login(email, password) {
    const r = await req('POST', '/auth/login', { email, password });
    if (r.ok) {
      setToken(r.data.token);
      setUser({ username: r.data.username, role: r.data.role, user_id: r.data.user_id });
    }
    return r;
  }

  async function signup(username, email, password) {
    return req('POST', '/auth/signup', { username, email, password });
  }

  function logout() {
    clearToken();
    redirectToLogin();
  }

  async function changePassword(old_password, new_password) {
    return req('POST', '/auth/change-password', { old_password, new_password }, true);
  }

  // ── Student profile ────────────────────────────────────────
  async function getMyProfile()          { return req('GET',  '/student/profile', null, true); }
  async function updateMyProfile(data)   { return req('PUT',  '/student/profile', data,  true); }
  async function registerStudent(data)   { return req('POST', '/student/register', data, true); }

  // ── Rooms (public) ─────────────────────────────────────────
  async function getRooms()              { return req('GET', '/rooms'); }
  async function getRoom(id)             { return req('GET', `/rooms/${id}`); }

  // ── Fees ───────────────────────────────────────────────────
  async function getMyFees()             { return req('GET', '/student/fees', null, true); }

  // ── Complaints ─────────────────────────────────────────────
  async function getMyComplaints()       { return req('GET', '/student/complaints', null, true); }
  async function submitComplaint(data)   { return req('POST', '/student/complaints', data, true); }

  // ── Admin ──────────────────────────────────────────────────
  async function adminGetStudents(approved)  { return req('GET', `/admin/students${approved !== undefined ? '?approved=' + approved : ''}`, null, true); }
  async function adminApproveStudent(id, is_approved) { return req('PATCH', `/admin/approve_student/${id}`, { is_approved }, true); }
  async function adminAllocateRoom(student_id, room_id) { return req('POST', '/admin/allocate_room', { student_id, room_id }, true); }
  async function adminAddRoom(data)      { return req('POST', '/admin/rooms', data, true); }
  async function adminUpdateRoom(id, data) { return req('PUT', `/admin/rooms/${id}`, data, true); }
  async function adminDeleteRoom(id)     { return req('DELETE', `/admin/rooms/${id}`, null, true); }
  async function adminGetFees()          { return req('GET', '/admin/fees', null, true); }
  async function adminCreateFee(data)    { return req('POST', '/admin/fees', data, true); }
  async function adminMarkFeePaid(id)    { return req('PATCH', `/admin/fees/${id}/mark_paid`, {}, true); }
  async function adminGetComplaints(status) { return req('GET', `/admin/complaints${status ? '?status=' + status : ''}`, null, true); }
  async function adminUpdateComplaint(id, data) { return req('PATCH', `/admin/complaints/${id}`, data, true); }
  async function adminDashboardStats()   { return req('GET', '/admin/dashboard_stats', null, true); }

  // ── Expose ─────────────────────────────────────────────────
  return {
    // helpers
    getToken, isLoggedIn, isAdmin, getUser, logout,
    requireLogin, redirectIfLoggedIn, toast,
    // auth
    login, signup, changePassword,
    // student
    getMyProfile, updateMyProfile, registerStudent,
    // rooms
    getRooms, getRoom,
    // fees & complaints
    getMyFees, getMyComplaints, submitComplaint,
    // admin
    adminGetStudents, adminApproveStudent, adminAllocateRoom,
    adminAddRoom, adminUpdateRoom, adminDeleteRoom,
    adminGetFees, adminCreateFee, adminMarkFeePaid,
    adminGetComplaints, adminUpdateComplaint, adminDashboardStats
  };

})();
