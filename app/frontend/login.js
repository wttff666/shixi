const form = document.querySelector("#loginForm");
const username = document.querySelector("#username");
const password = document.querySelector("#password");
const errorElement = document.querySelector("#loginError");

if (getAuth()?.user) {
  authJson("/api/auth/me")
    .then(() => {
      location.href = "/";
    })
    .catch(() => {
      clearAuth();
    });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorElement.textContent = "";
  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: username.value.trim(),
        password: password.value,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "登录失败");
    setAuth({ user: data.user });
    if (data.user.must_change_password) {
      const changed = prompt("请设置新密码（至少 8 位）");
      if (!changed || changed.length < 8) {
        clearAuth();
        throw new Error("首次登录必须修改密码");
      }
      const changeResponse = await authJson("/api/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: changed }),
      });
      if (!changeResponse.ok) throw new Error("密码修改失败");
      const auth = getAuth();
      auth.user.must_change_password = false;
      setAuth(auth);
    }
    location.href = "/";
  } catch (error) {
    errorElement.textContent = error.message;
  }
});
