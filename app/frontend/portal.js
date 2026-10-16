const auth = requireAuth();

const machineList = document.querySelector("#portalMachines");
const requestList = document.querySelector("#portalRequests");
const customerLabel = document.querySelector("#portalCustomer");
const toast = document.querySelector("#toast");

document.querySelector("#logoutButton").addEventListener("click", logout);

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 2200);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function statusBadge(status) {
  const map = {
    待研判: "badge-medium",
    待派工: "badge-high",
    已派工: "badge-remote",
    已研判: "badge-remote",
    已关闭: "badge-low",
  };
  return `<span class="badge ${map[status] || "badge-low"}">${escapeHtml(status)}</span>`;
}

async function loadPortal() {
  machineList.innerHTML = '<div class="loading-block">正在读取...</div>';
  requestList.innerHTML = '<div class="loading-block">正在读取...</div>';
  try {
    const [machines, requests] = await Promise.all([
      authJson("/api/machines"),
      authJson("/api/service-requests"),
    ]);

    machineList.innerHTML = "";
    if (!machines.length) {
      machineList.innerHTML = '<div class="empty-block">暂无设备记录</div>';
    }
    machines.forEach((machine) => {
      const article = document.createElement("article");
      article.className = "document-card";
      article.innerHTML = `
        <div class="document-main">
          <div class="file-mark">EQ</div>
          <div class="document-copy">
            <strong>${escapeHtml(machine.machine_code)} · ${escapeHtml(machine.model_code)}</strong>
            <p>${escapeHtml(machine.site_name)} ${escapeHtml(machine.line_name)}</p>
            <small>投产 ${escapeHtml(machine.install_date)} · 保修截止 ${escapeHtml(machine.warranty_end)}</small>
          </div>
        </div>
        <div class="document-actions">
          <span class="status-badge ${machine.warranty_status === "保修内" ? "published" : "disabled"}">${escapeHtml(machine.warranty_status)}</span>
        </div>`;
      machineList.append(article);
    });

    requestList.innerHTML = "";
    if (!requests.length) {
      requestList.innerHTML = '<div class="empty-block">暂无服务记录</div>';
    }
    requests.forEach((row) => {
      const article = document.createElement("article");
      article.className = "document-card";
      article.innerHTML = `
        <div class="document-main">
          <div class="file-mark">SR</div>
          <div class="document-copy">
            <strong>${escapeHtml(row.request_no)} · ${escapeHtml(row.machine_code)}</strong>
            <p>${escapeHtml(row.symptom.slice(0, 70))}</p>
            <small>${new Date(row.created_at).toLocaleString("zh-CN", { hour12: false })}</small>
          </div>
        </div>
        <div class="document-actions">${statusBadge(row.status)}</div>
        ${
          row.customer_reply
            ? `<pre class="portal-reply">${escapeHtml(row.customer_reply)}</pre>`
            : ""
        }`;
      requestList.append(article);
    });
  } catch (error) {
    showToast(`读取失败：${error.message}`);
  }
}

customerLabel.textContent = auth.user.customer_name || auth.user.username;
document.querySelector("#refreshPortal").addEventListener("click", loadPortal);
loadPortal();
