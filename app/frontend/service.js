const auth = requireAuth(["agent", "tech", "supervisor", "sys_admin"]);

const createForm = document.querySelector("#createForm");
const customerSelect = document.querySelector("#newCustomer");
const machineSelect = document.querySelector("#newMachine");
const channelSelect = document.querySelector("#newChannel");
const prioritySelect = document.querySelector("#newPriority");
const symptomInput = document.querySelector("#newSymptom");
const statusFilter = document.querySelector("#statusFilter");
const requestList = document.querySelector("#requestList");
const detailPanel = document.querySelector("#detailPanel");
const detailTitle = document.querySelector("#detailTitle");
const detailBody = document.querySelector("#detailBody");
const detailActions = document.querySelector("#detailActions");
const toast = document.querySelector("#toast");

let customers = [];
let machines = [];
let options = { status: [], channel: [], priority: [] };
let currentRequest = null;

if (auth.user.role !== "sys_admin") {
  document.querySelectorAll("[data-sysadmin]").forEach((element) => {
    element.hidden = true;
  });
}

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

function fillSelect(element, values, keepEmpty = false) {
  element.innerHTML = keepEmpty ? '<option value="">全部状态</option>' : "";
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    element.append(option);
  });
}

function renderMachines() {
  const customer = customerSelect.value;
  const rows = machines.filter((item) => item.customer_name === customer);
  machineSelect.innerHTML = "";
  rows.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.machine_code;
    option.textContent = `${item.machine_code} · ${item.model_code} · ${item.line_name}`;
    machineSelect.append(option);
  });
}

async function loadBase() {
  [customers, machines, options] = await Promise.all([
    authJson("/api/customers"),
    authJson("/api/machines"),
    authJson("/api/service-requests/options"),
  ]);
  fillSelect(customerSelect, customers.map((item) => item.name));
  fillSelect(channelSelect, options.channel);
  fillSelect(prioritySelect, options.priority);
  fillSelect(statusFilter, options.status, true);
  renderMachines();
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

async function loadRequests() {
  requestList.innerHTML = '<div class="loading-block">正在读取工单...</div>';
  const query = statusFilter.value
    ? `?status=${encodeURIComponent(statusFilter.value)}`
    : "";
  try {
    const rows = await authJson(`/api/service-requests${query}`);
    requestList.innerHTML = "";
    if (!rows.length) {
      requestList.innerHTML = '<div class="empty-block">暂无工单</div>';
      return;
    }
    rows.forEach((row) => {
      const article = document.createElement("article");
      article.className = "document-card";
      article.innerHTML = `
        <div class="document-main">
          <div class="file-mark">SR</div>
          <div class="document-copy">
            <strong>${escapeHtml(row.request_no)} · ${escapeHtml(row.machine_code)}</strong>
            <p>${escapeHtml(row.customer_name)} · ${escapeHtml(row.channel)} · ${escapeHtml(row.priority)}</p>
            <small>${escapeHtml(row.symptom.slice(0, 60))}${
              row.fault_name ? " · 初判：" + escapeHtml(row.fault_name) : ""
            }</small>
          </div>
        </div>
        <div class="document-actions">
          ${statusBadge(row.status)}
          <button type="button" data-open="${row.id}">查看</button>
        </div>`;
      requestList.append(article);
    });
  } catch (error) {
    requestList.innerHTML = `<div class="empty-block">读取失败：${escapeHtml(error.message)}</div>`;
  }
}

function renderDetail(row) {
  currentRequest = row;
  detailPanel.hidden = false;
  detailTitle.textContent = `${row.request_no} · ${row.machine_code}`;
  detailActions.innerHTML = `
    <button type="button" data-status="已派工">标记已派工</button>
    <button type="button" class="danger" data-status="已关闭">关闭工单</button>
    <a class="secondary-button" href="/">去诊断</a>`;

  const dispatch = row.dispatch || {};
  const dispatchRows = [];
  const addDispatch = (label, value) => {
    if (value) dispatchRows.push(`<div><dt>${label}</dt><dd>${escapeHtml(value)}</dd></div>`);
  };
  addDispatch("处理方式", dispatch.mode);
  addDispatch("判定依据", dispatch.reason);
  addDispatch("服务等级", dispatch.sla);
  addDispatch("预计工时", dispatch.eta_hours);
  addDispatch("工时依据", dispatch.eta_basis);

  const parts = (dispatch.parts || [])
    .map((item) => `${escapeHtml(item.part_no)} ${escapeHtml(item.name)}（库存 ${item.stock}，货期 ${item.lead_days} 天）`)
    .join("<br>");

  const notes = (row.internal_notes || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");

  const citations = (row.citations || [])
    .map(
      (item, index) =>
        `<li>[${index + 1}] ${escapeHtml(item.ref || "")}</li>`,
    )
    .join("");

  detailBody.innerHTML = `
    <dl class="diagnosis-grid">
      <div><dt>客户</dt><dd>${escapeHtml(row.customer_name)}</dd></div>
      <div><dt>机型</dt><dd>${escapeHtml(row.model_code)}</dd></div>
      <div><dt>来源</dt><dd>${escapeHtml(row.channel)}</dd></div>
      <div><dt>优先级</dt><dd>${escapeHtml(row.priority)}</dd></div>
      <div><dt>状态</dt><dd>${statusBadge(row.status)}</dd></div>
      <div><dt>处理人</dt><dd>${escapeHtml(row.handler_name || "-")}</dd></div>
      <div><dt>初步故障</dt><dd>${escapeHtml(row.fault_id ? row.fault_id + " " + row.fault_name : "未研判")}</dd></div>
      <div><dt>置信度</dt><dd>${escapeHtml(row.confidence || "-")}</dd></div>
    </dl>
    <div class="diagnosis-block">
      <h4>客户描述</h4>
      <p>${escapeHtml(row.symptom)}</p>
    </div>
    ${
      dispatchRows.length
        ? `<section class="dispatch-block">
             <h4>派工建议${dispatch.second_line ? '<span class="badge badge-medium">建议二线复核</span>' : ""}</h4>
             <dl class="diagnosis-grid">${dispatchRows.join("")}</dl>
             ${parts ? `<div class="diagnosis-block"><h4>建议备件</h4><p>${parts}</p></div>` : ""}
             ${dispatch.second_line_reason ? `<p class="dispatch-note">${escapeHtml(dispatch.second_line_reason)}</p>` : ""}
           </section>`
        : '<div class="empty-block">尚未诊断，未生成派工建议</div>'
    }
    ${notes ? `<section class="internal-block"><header><h4>内部备注</h4><span class="tag-internal">仅内部可见</span></header><ul>${notes}</ul></section>` : ""}
    ${
      row.customer_reply
        ? `<section class="reply-block">
             <header><h4>对客户说明</h4><button type="button" class="secondary-button" data-copy-reply>复制</button></header>
             <pre>${escapeHtml(row.customer_reply)}</pre>
           </section>`
        : ""
    }
    ${citations ? `<div class="diagnosis-block"><h4>依据引用</h4><ul>${citations}</ul></div>` : ""}
    ${row.closed_note ? `<div class="diagnosis-block"><h4>关闭备注</h4><p>${escapeHtml(row.closed_note)}</p></div>` : ""}`;
}

async function openRequest(requestId) {
  try {
    renderDetail(await authJson(`/api/service-requests/${requestId}`));
    detailPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showToast(`读取工单失败：${error.message}`);
  }
}

createForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const symptom = symptomInput.value.trim();
  if (!symptom) {
    showToast("请填写现象描述");
    return;
  }
  try {
    const row = await authJson("/api/service-requests", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        customer_name: customerSelect.value,
        machine_code: machineSelect.value,
        channel: channelSelect.value,
        priority: prioritySelect.value,
        symptom,
      }),
    });
    symptomInput.value = "";
    showToast(`工单 ${row.request_no} 已创建`);
    await loadRequests();
    await openRequest(row.id);
  } catch (error) {
    showToast(`创建失败：${error.message}`);
  }
});

customerSelect.addEventListener("change", renderMachines);
statusFilter.addEventListener("change", loadRequests);
document.querySelector("#refreshRequests").addEventListener("click", loadRequests);
document.querySelector("#logoutButton").addEventListener("click", logout);

requestList.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-open]");
  if (button) openRequest(Number(button.dataset.open));
});

detailActions.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-status]");
  if (!button || !currentRequest) return;
  const status = button.dataset.status;
  let closedNote = "";
  if (status === "已关闭") {
    closedNote = prompt("关闭备注（可留空）") || "";
  }
  try {
    const row = await authJson(`/api/service-requests/${currentRequest.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, closed_note: closedNote }),
    });
    renderDetail(row);
    await loadRequests();
    showToast(`工单已更新为「${status}」`);
  } catch (error) {
    showToast(`更新失败：${error.message}`);
  }
});

detailBody.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy-reply]");
  if (!button) return;
  const text = button.closest(".reply-block")?.querySelector("pre")?.textContent || "";
  try {
    await navigator.clipboard.writeText(text);
    showToast("已复制，可直接发给客户");
  } catch {
    showToast("复制失败，请手动选中文本");
  }
});

loadBase()
  .then(loadRequests)
  .catch((error) => showToast(`初始化失败：${error.message}`));
