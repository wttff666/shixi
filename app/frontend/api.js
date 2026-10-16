const AUTH_KEY = "remotediag-auth-v1";

function getAuth() {
  try {
    return JSON.parse(localStorage.getItem(AUTH_KEY) || "null");
  } catch {
    return null;
  }
}

function setAuth(value) {
  const user = value?.user || value;
  localStorage.setItem(AUTH_KEY, JSON.stringify({ user }));
}

function clearAuth() {
  localStorage.removeItem(AUTH_KEY);
}

function authHeaders(extra = {}) {
  return { ...extra };
}

function redirectLogin() {
  if (!location.pathname.endsWith("/login")) {
    location.href = "/login";
  }
}

function requireAuth(roles = null) {
  const auth = getAuth();
  if (!auth?.user) {
    redirectLogin();
    return null;
  }
  if (roles && !roles.includes(auth.user.role)) {
    alert("当前账号没有访问该页面的权限");
    location.href = "/";
    return null;
  }
  return auth;
}

async function authFetch(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    credentials: "include",
    headers: authHeaders(options.headers || {}),
  });
  if (response.status === 401) {
    clearAuth();
    redirectLogin();
    throw new Error("登录已过期");
  }
  return response;
}

async function authJson(url, options = {}) {
  const response = await authFetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `HTTP ${response.status}`);
  }
  return data;
}

async function logout() {
  try {
    await authFetch("/api/auth/logout", { method: "POST" });
  } catch {
    // Ignore network errors while logging out.
  }
  clearAuth();
  redirectLogin();
}
