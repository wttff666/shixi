const auth = requireAuth();
const PRESETS = window.DEMO_DATA.presets;

const el = (id) => document.querySelector(`#${id}`);

const queueElement = el("queue");
const queueBadge = el("queueBadge");
const headTitle = el("headTitle");
const headSub = el("headSub");
const headTags = el("headTags");
const messagesElement = el("messages");
const composer = el("composer");
const questionInput = el("questionInput");
const sendButton = el("sendButton");
const stopButton = el("stopButton");
const newChatButton = el("newChatButton");
const statusText = el("statusText");
const modelState = el("modelState");
const skillSelect = el("skillSelect");
const answerMode = el("answerMode");
const chatAvatar = el("chatAvatar");
const chatTitle = el("chatTitle");
const chatMeta = el("chatMeta");
const verdictEmpty = el("verdictEmpty");
const verdictBody = el("verdictBody");
const dispatchCard = el("dispatchCard");
const dispatchFlag = el("dispatchFlag");
const dispatchBody = el("dispatchBody");
const internalCard = el("internalCard");
const internalBody = el("internalBody");
const replyCard = el("replyCard");
const replyBody = el("replyBody");
const copyReply = el("copyReply");
const refsCard = el("refsCard");
const refCount = el("refCount");
const refBody = el("refBody");
const toast = el("toast");
const logoutButton = el("logoutButton");

if (!["kb_admin", "sys_admin"].includes(auth.user.role)) {
  document.querySelectorAll("[data-internal]").forEach((node) => {
    node.hidden = true;
  });
}
if (auth.user.role !== "sys_admin") {
  document.querySelectorAll("[data-sysadmin]").forEach((node) => {
    node.hidden = true;
  });
}

let requests = [];
let currentRequest = null;
let currentConversation = null;
let currentMessages = [];
let currentDiagnosis = null;
let activeController = null;
let busy = false;

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

function renderInline(value) {
  return escapeHtml(value)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function renderMarkdown(value) {
  if (!value) return "";
  const lines = String(value).replaceAll("\r", "").split("\n");
  const html = [];
  let listType = null;
  let inCode = false;
  let codeLines = [];

  const closeList = () => {
    if (listType) {
      html.push(`</${listType}>`);
      listType = null;
    }
  };

  lines.forEach((line) => {
    if (line.trim().startsWith("```")) {
      if (inCode) {
        html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
        codeLines = [];
        inCode = false;
      } else {
        closeList();
        inCode = true;
      }
      return;
    }
    if (inCode) {
      codeLines.push(line);
      return;
    }
    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      closeList();
      const level = Math.min(heading[1].length + 1, 4);
      html.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
      return;
    }
    const bullet = line.match(/^\s*[-*]\s+(.+)$/);
    if (bullet) {
      if (listType !== "ul") {
        closeList();
        html.push("<ul>");
        listType = "ul";
      }
      html.push(`<li>${renderInline(bullet[1])}</li>`);
      return;
    }
    const numbered = line.match(/^\s*\d+\.\s+(.+)$/);
    if (numbered) {
      if (listType !== "ol") {
        closeList();
        html.push("<ol>");
        listType = "ol";
      }
      html.push(`<li>${renderInline(numbered[1])}</li>`);
      return;
    }
    if (!line.trim()) {
      closeList();
      return;
    }
    closeList();
    html.push(`<p>${renderInline(line)}</p>`);
  });
  closeList();
  return html.join("");
}

/* ---------- 进度 ---------- */

function resetSteps() {
  document.querySelectorAll(".step").forEach((node) => {
    node.classList.remove("done", "active");
  });
  document.querySelectorAll(".step-bar").forEach((node) => {
    node.classList.remove("done");
  });
}

function setStep(active, finishedAll = false) {
  document.querySelectorAll(".step").forEach((node) => {
    const index = Number(node.dataset.step);
    node.classList.toggle("done", finishedAll || index < active);
    node.classList.toggle("active", !finishedAll && index === active);
    const dot = node.querySelector(".dot");
    if (dot) dot.textContent = finishedAll || index < active ? "✓" : String(index);
  });
  document.querySelectorAll(".step-bar").forEach((node) => {
    const index = Number(node.dataset.bar);
    node.classList.toggle("done", finishedAll || index < active);
  });
}

/* ---------- 工单队列 ---------- */

function statusBadge(status) {
  const map = {
    待研判: "badge-medium",
    待派工: "badge-high",
    已派工: "badge-info",
    已研判: "badge-info",
    已关闭: "badge-low",
  };
  return `<span class="badge ${map[status] || "badge-low"}">${escapeHtml(status)}</span>`;
}

function renderQueue() {
  queueBadge.textContent = String(requests.filter((item) => item.status !== "已关闭").length);
  queueElement.innerHTML = "";
  if (!requests.length) {
    queueElement.innerHTML = '<p class="q-meta" style="padding:8px 11px">暂无工单</p>';
    return;
  }
  requests.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className =
      "q-item" + (currentRequest && currentRequest.id === item.id ? " active" : "");
    button.innerHTML = `
      <span class="q-top"><span class="q-no">${escapeHtml(item.request_no)}</span>${statusBadge(item.status)}</span>
      <span class="q-meta">${escapeHtml(item.machine_code)} · ${escapeHtml(item.customer_name)}</span>
      <span class="q-meta">${escapeHtml(
        item.fault_name ? `${item.fault_id} ${item.fault_name}` : "未研判",
      )}${item.on_site ? " · " + (item.on_site === "是" ? "建议到场" : "远程可处理") : ""}</span>`;
    button.addEventListener("click", () => selectRequest(item));
    queueElement.append(button);
  });
}

function renderHead() {
  if (!currentRequest) {
    headTitle.textContent = "未选择工单";
    headSub.textContent = "从左侧选择工单，或直接输入客户描述发起诊断";
    headTags.innerHTML = "";
    return;
  }
  headTitle.textContent = `${currentRequest.request_no} · ${currentRequest.machine_code}`;
  headSub.textContent = `${currentRequest.customer_name} · ${currentRequest.model_code} · 来源 ${currentRequest.channel} · 处理人 ${currentRequest.handler_name || "-"}`;
  headTags.innerHTML = [
    statusBadge(currentRequest.status),
    currentRequest.priority ? `<span class="badge badge-low">优先级 ${escapeHtml(currentRequest.priority)}</span>` : "",
    currentRequest.confidence
      ? `<span class="badge badge-info">置信 ${escapeHtml(currentRequest.confidence)}</span>`
      : "",
  ].join("");
}

/* ---------- 右栏结论 ---------- */

function resetDiagnosisPanel() {
  currentDiagnosis = null;
  verdictEmpty.hidden = false;
  verdictBody.hidden = true;
  verdictBody.innerHTML = "";
  dispatchCard.hidden = true;
  internalCard.hidden = true;
  replyCard.hidden = true;
  refsCard.hidden = true;
  replyBody.textContent = "";
  dispatchBody.innerHTML = "";
  internalBody.innerHTML = "";
  refBody.innerHTML = "";
}

function renderDiagnosis(data) {
  if (!data) return;
  currentDiagnosis = data;

  const tags = [];
  if (data.confidence) {
    const cls =
      data.confidence === "high"
        ? "badge-high"
        : data.confidence === "medium"
          ? "badge-medium"
          : "badge-low";
    const label = { high: "置信 高", medium: "置信 中", low: "置信 低" }[data.confidence] || "待确认";
    tags.push(`<span class="badge ${cls}">${label}</span>`);
  }
  if (data.on_site) {
    tags.push(
      `<span class="badge ${data.on_site === "是" ? "badge-onsite" : "badge-remote"}">${
        data.on_site === "是" ? "需到场" : "远程可处理"
      }</span>`,
    );
  }
  if (data.warranty && data.warranty.status) {
    tags.push(`<span class="badge badge-info">${escapeHtml(data.warranty.status)}</span>`);
  }
  if (data.service_request_no) {
    tags.push(`<span class="badge badge-low">工单 ${escapeHtml(data.service_request_no)}</span>`);
  }

  const kv = [];
  const addKv = (label, value) => {
    if (value) kv.push(`<dt>${label}</dt><dd>${escapeHtml(value)}</dd>`);
  };
  addKv("手册章节", data.manual_section);
  addKv("严重度", data.severity);
  addKv("典型原因", data.cause);
  addKv("处置要点", data.action);
  if (data.warranty) addKv("结算方式", data.warranty.settlement);
  if (data.warranty) addKv("服务等级", data.warranty.service_level);

  verdictEmpty.hidden = true;
  verdictBody.hidden = false;
  verdictBody.innerHTML = `
    <div class="verdict-title"><span>${escapeHtml(data.fault_id || "待确认")}</span>${escapeHtml(
      data.fault_name || "尚未定位到具体故障",
    )}</div>
    <div class="wb-tags">${tags.join("")}</div>
    ${kv.length ? `<dl class="kv">${kv.join("")}</dl>` : ""}`;

  const dispatch = data.dispatch || {};
  const rows = [];
  const addRow = (label, value, mono = false) => {
    if (value) rows.push(`<dt>${label}</dt><dd class="${mono ? "num" : ""}">${escapeHtml(value)}</dd>`);
  };
  addRow("处理方式", dispatch.mode);
  addRow("判定依据", dispatch.reason);
  addRow("服务等级", dispatch.sla, true);
  addRow("预计工时", dispatch.eta_hours, true);
  addRow("工时依据", dispatch.eta_basis);
  const parts = (dispatch.parts || [])
    .map(
      (part) =>
        `${part.part_no} ${part.name} · 库存 ${part.stock} · 货期 ${part.lead_days} 天`,
    )
    .join("<br>");
  if (rows.length) {
    dispatchFlag.innerHTML = dispatch.second_line
      ? '<span class="badge badge-medium">建议二线复核</span>'
      : "";
    dispatchBody.innerHTML =
      `<dl class="dispatch-grid">${rows.join("")}</dl>` +
      (parts ? `<dt class="kicker" style="margin-top:10px">建议备件</dt><p>${parts}</p>` : "") +
      (dispatch.second_line_reason
        ? `<p class="dispatch-note" style="margin:10px 0 0">${escapeHtml(dispatch.second_line_reason)}</p>`
        : "");
    dispatchCard.hidden = false;
  } else {
    dispatchCard.hidden = true;
  }

  const notes = data.internal_notes || [];
  internalBody.innerHTML = notes.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  internalCard.hidden = notes.length === 0;

  replyBody.textContent = data.customer_reply || "";
  replyCard.hidden = !data.customer_reply;

  const citations = data.citations || [];
  refCount.textContent = String(citations.length);
  refBody.innerHTML = citations
    .map((item, index) => `<li>[${index + 1}] ${escapeHtml(item.ref || item.source || "")}</li>`)
    .join("");
  refsCard.hidden = citations.length === 0;
}

/* ---------- 会话 ---------- */

function renderMessages() {
  messagesElement.innerHTML = "";
  if (!currentMessages.length) {
    messagesElement.innerHTML = `
      <div class="who" style="padding:4px 0 6px">还没有提问。把客户口述的现象贴进来，系统会结合设备档案与实时数据给出初步判断。</div>`;
    return;
  }
  currentMessages.forEach((message) => appendMessage(message.role, message.content));
  scrollToBottom();
}

function appendMessage(role, content, isStreaming = false) {
  const turn = document.createElement("div");
  turn.className = "turn";
  const who = document.createElement("div");
  who.className = "who";
  who.textContent = role === "user" ? "客户口述" : "诊断助手";
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role === "user" ? "me" : "bot"}`;
  bubble.innerHTML = role === "assistant" ? renderMarkdown(content) : escapeHtml(content);
  turn.append(who, bubble);
  let statusElement = null;
  if (isStreaming) {
    statusElement = document.createElement("div");
    statusElement.className = "message-status";
    statusElement.textContent = "正在读取设备与资料…";
    turn.append(statusElement);
  }
  messagesElement.append(turn);
  scrollToBottom();
  return { turn, bubble, statusElement };
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    messagesElement.scrollTop = messagesElement.scrollHeight;
  });
}

function autoResize() {
  questionInput.style.height = "auto";
  questionInput.style.height = `${Math.min(questionInput.scrollHeight, 160)}px`;
}

function setBusy(value) {
  busy = value;
  sendButton.disabled = value;
  stopButton.hidden = !value;
  questionInput.disabled = value;
}

function setStatus(text) {
  statusText.textContent = text || "检索范围：已发布知识库";
}

function parseEvents(buffer, onEvent) {
  const lines = buffer.split("\n");
  const remainder = lines.pop() || "";
  lines
    .filter(Boolean)
    .forEach((line) => {
      let event;
      try {
        event = JSON.parse(line);
      } catch {
        return;
      }
      onEvent(event);
    });
  return remainder;
}

async function readStream(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = parseEvents(buffer, onEvent);
  }
}

async function loadRequests() {
  try {
    requests = await authJson("/api/service-requests?limit=100");
  } catch {
    requests = [];
  }
  renderQueue();
}

async function newConversation() {
  currentConversation = await authJson("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: currentRequest ? currentRequest.request_no : "新诊断" }),
  });
  currentMessages = [];
  chatMeta.textContent = "等待输入";
  resetSteps();
  resetDiagnosisPanel();
  renderMessages();
  return currentConversation;
}

async function selectRequest(request) {
  currentRequest = request;
  renderQueue();
  renderHead();
  chatAvatar.textContent = "客";
  chatTitle.textContent = `${request.machine_code} · 客户口述`;
  resetSteps();
  resetDiagnosisPanel();
  if (request.conversation_id) {
    try {
      const detail = await authJson(`/api/conversations/${request.conversation_id}`);
      currentConversation = detail;
      currentMessages = detail.messages.map((message) => ({
        role: message.role,
        content: message.content,
      }));
      const last = [...detail.messages]
        .reverse()
        .find((message) => message.role === "assistant" && message.meta?.diagnosis);
      if (last) {
        renderDiagnosis(last.meta.diagnosis);
        setStep(4, true);
        chatMeta.textContent = `已有诊断 · ${new Date(last.created_at).toLocaleString("zh-CN", { hour12: false })}`;
      }
      renderMessages();
      return;
    } catch {
      // 会话已删除，继续走新建流程
    }
  }
  currentConversation = null;
  currentMessages = [];
  questionInput.value = request.symptom || "";
  autoResize();
  renderMessages();
  questionInput.focus();
}

async function sendQuestion(question) {
  if (!currentConversation) {
    await newConversation();
  }
  currentMessages.push({ role: "user", content: question });
  renderMessages();
  resetDiagnosisPanel();
  resetSteps();
  setStep(1);
  const assistant = appendMessage("assistant", "", true);
  activeController = new AbortController();
  setBusy(true);

  try {
    const response = await authFetch("/api/diagnosis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: question,
        service_request_id: currentRequest ? currentRequest.id : null,
        skill_id: skillSelect.value || null,
        answer_mode: answerMode.value,
        conversation_id: currentConversation.id,
      }),
      signal: activeController.signal,
    });
    if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);

    let answer = "";
    await readStream(response, (event) => {
      if (event.type === "conversation") {
        currentConversation = { ...currentConversation, id: event.id, title: event.title };
      } else if (event.type === "skill") {
        setStatus(event.matched ? `使用 Skill：${event.name}` : "自动诊断模式");
        setStep(1);
      } else if (event.type === "machine") {
        chatTitle.textContent = `${event.machine_code} · ${event.model_code}`;
        setStep(2);
      } else if (event.type === "tool") {
        setStatus(event.ok ? `已调用工具：${event.name}` : `工具失败：${event.name}`);
        setStep(2);
      } else if (event.type === "status") {
        assistant.statusElement.textContent = event.text;
        setStatus(event.text);
        setStep(String(event.text).includes("生成") ? 4 : 3);
      } else if (event.type === "citations") {
        refCount.textContent = String((event.items || []).length);
        refBody.innerHTML = (event.items || [])
          .map((item, index) => `<li>[${index + 1}] ${escapeHtml(item.ref || item.source || "")}</li>`)
          .join("");
        refsCard.hidden = !(event.items || []).length;
      } else if (event.type === "diagnosis") {
        renderDiagnosis(event.data);
        setStep(4, true);
      } else if (event.type === "delta") {
        answer += event.text || "";
        assistant.bubble.innerHTML = renderMarkdown(answer);
        scrollToBottom();
      } else if (event.type === "error") {
        throw new Error(event.message || "诊断失败");
      }
    });

    if (!answer.trim()) {
      answer = "本次没有生成有效回答，请补充信息后重试。";
      assistant.bubble.innerHTML = renderMarkdown(answer);
    }
    assistant.statusElement?.remove();
    currentMessages.push({ role: "assistant", content: answer });
    if (currentDiagnosis?.service_request_no) {
      chatMeta.textContent = `已回写 ${currentDiagnosis.service_request_no}`;
    }
    await loadRequests();
  } catch (error) {
    if (error.name === "AbortError") {
      assistant.statusElement.textContent = "已停止生成";
    } else {
      assistant.bubble.textContent = `诊断失败：${error.message}`;
      assistant.statusElement?.remove();
    }
  } finally {
    activeController = null;
    setBusy(false);
    setStatus("");
    questionInput.focus();
  }
}

/* ---------- 事件绑定 ---------- */

composer.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question || busy) return;
  questionInput.value = "";
  autoResize();
  sendQuestion(question);
});

questionInput.addEventListener("input", autoResize);
questionInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});

stopButton.addEventListener("click", () => activeController?.abort());
newChatButton.addEventListener("click", () => {
  currentRequest = currentRequest ? { ...currentRequest } : null;
  renderQueue();
  newConversation().catch((error) => showToast(error.message));
});
logoutButton.addEventListener("click", logout);
copyReply.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(replyBody.textContent || "");
    showToast("已复制，可直接发给客户");
  } catch {
    showToast("复制失败，请手动选中文本");
  }
});

document.querySelectorAll(".q-meta").forEach(() => {});

authJson("/api/health")
  .then((data) => {
    modelState.textContent = data.model_configured ? "模型已连接" : "本地模式";
    modelState.className = `badge ${data.model_configured ? "badge-info" : "badge-low"}`;
  })
  .catch(() => {
    modelState.textContent = "服务未连接";
    modelState.className = "badge badge-onsite";
  });

authJson("/api/skills")
  .then((skills) => {
    skills
      .filter((skill) => skill.status === "published")
      .forEach((skill) => {
        const option = document.createElement("option");
        option.value = skill.skill_id;
        option.textContent = `${skill.name} · v${skill.version}`;
        skillSelect.append(option);
      });
  })
  .catch(() => {});

async function init() {
  await loadRequests();
  const open = requests.find((item) => item.status !== "已关闭") || requests[0];
  if (open) {
    await selectRequest(open);
  } else {
    renderHead();
    renderMessages();
    await newConversation();
  }
}

init().catch((error) => showToast(`初始化失败：${error.message}`));
