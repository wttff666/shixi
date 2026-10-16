const auth = requireAuth(["sys_admin"]);
const userForm = document.querySelector("#userForm");
const userList = document.querySelector("#userList");
const toast = document.querySelector("#toast");

document.querySelector("#logoutButton").addEventListener("click", logout);

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 1800);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function loadUsers() {
  userList.innerHTML = `<div class="loading-block">正在读取用户...</div>`;
  try {
    const users = await authJson("/api/admin/users");
    renderUsers(users);
  } catch (error) {
    userList.innerHTML = `<div class="empty-block">读取失败：${escapeHtml(error.message)}</div>`;
  }
}

function renderUsers(users) {
  userList.innerHTML = "";
  users.forEach((user) => {
    const article = document.createElement("article");
    article.className = "document-card";
    article.innerHTML = `
      <div class="document-main">
        <div class="file-mark">US</div>
        <div class="document-copy">
          <strong>${escapeHtml(user.username)}</strong>
          <p>${escapeHtml(user.role_label)}${user.customer_name ? " · " + escapeHtml(user.customer_name) : ""} · 创建于 ${new Date(user.created_at).toLocaleString("zh-CN", { hour12: false })}</p>
          <small>${user.must_change_password ? "首次登录需修改密码" : "密码已初始化"}</small>
        </div>
      </div>
      <div class="document-actions">
        <span class="status-badge ${user.active ? "published" : "disabled"}">${user.active ? "启用" : "停用"}</span>
        <button type="button" data-action="reset" data-id="${user.id}">重置密码</button>
        <button type="button" data-action="logout" data-id="${user.id}">强制退出</button>
        <button type="button" class="${user.active ? "danger" : ""}" data-action="toggle" data-id="${user.id}" data-active="${user.active}">${user.active ? "停用" : "启用"}</button>
      </div>`;
    userList.append(article);
  });
}

userForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await authJson("/api/admin/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: document.querySelector("#newUsername").value.trim(),
        password: document.querySelector("#newPassword").value,
        role: document.querySelector("#newRole").value,
        customer_name: document.querySelector("#newCustomer").value.trim(),
      }),
    });
    userForm.reset();
    showToast("用户已创建");
    await loadUsers();
  } catch (error) {
    showToast(`创建失败：${error.message}`);
  }
});

userList.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const userId = Number(button.dataset.id);
  const action = button.dataset.action;
  try {
    if (action === "reset") {
      const password = prompt("请输入新的临时密码（至少 8 位）");
      if (!password) return;
      await authJson(`/api/admin/users/${userId}/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      showToast("密码已重置，用户下次登录必须修改");
    } else if (action === "logout") {
      await authJson(`/api/admin/users/${userId}/logout`, { method: "POST" });
      showToast("该用户会话已清除");
    } else if (action === "toggle") {
      const active = button.dataset.active !== "true";
      await authJson(`/api/admin/users/${userId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active }),
      });
      showToast(active ? "用户已启用" : "用户已停用");
    }
    await loadUsers();
  } catch (error) {
    showToast(`操作失败：${error.message}`);
  }
});

document.querySelector("#refreshUsers").addEventListener("click", loadUsers);
loadUsers();
