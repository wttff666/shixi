const uploadForm = document.querySelector("#uploadForm");
const fileInput = document.querySelector("#documentFile");
const dropZone = document.querySelector("#dropZone");
const selectedFile = document.querySelector("#selectedFile");
const uploadButton = document.querySelector("#uploadButton");
const uploadProgress = document.querySelector("#uploadProgress");
const uploadProgressBar = document.querySelector("#uploadProgressBar");
const uploadProgressText = document.querySelector("#uploadProgressText");
const documentList = document.querySelector("#documentList");
const chunkDrawer = document.querySelector("#chunkDrawer");
const chunkList = document.querySelector("#chunkList");
const chunkDrawerTitle = document.querySelector("#chunkDrawerTitle");
const chunkDrawerMeta = document.querySelector("#chunkDrawerMeta");
const ocrDrawer = document.querySelector("#ocrDrawer");
const ocrPageList = document.querySelector("#ocrPageList");
const ocrDrawerTitle = document.querySelector("#ocrDrawerTitle");
const ocrDrawerMeta = document.querySelector("#ocrDrawerMeta");
const saveOcrPages = document.querySelector("#saveOcrPages");
const toast = document.querySelector("#toast");
const auth = requireAuth(["kb_admin", "sys_admin"]);
document.querySelector("#logoutButton")?.addEventListener("click", logout);
if (auth.user.role !== "sys_admin") {
  document.querySelectorAll("[data-sysadmin]").forEach((element) => {
    element.hidden = true;
  });
}

const STATUS_LABELS = {
  uploaded: "已上传",
  parsed: "已解析",
  preview_ready: "待发布",
  published: "已发布",
  failed: "处理失败",
  ocr_required: "需要 OCR",
  ocr_pending: "OCR 处理中",
};

let currentOcrDocumentId = null;

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 1800);
}

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(value) {
  if (!value) return "";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function setSelectedFile(file) {
  selectedFile.textContent = file ? `${file.name} · ${formatBytes(file.size)}` : "尚未选择文件";
}

fileInput.addEventListener("change", () => setSelectedFile(fileInput.files[0]));

["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragging");
  });
});
["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragging");
  });
});
dropZone.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (!file) return;
  const transfer = new DataTransfer();
  transfer.items.add(file);
  fileInput.files = transfer.files;
  setSelectedFile(file);
});

async function loadDocuments() {
  documentList.innerHTML = `<div class="loading-block">正在读取文档...</div>`;
  try {
    const response = await authFetch("/api/documents");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const documents = await response.json();
    renderDocuments(documents);
  } catch (error) {
    documentList.innerHTML = `<div class="empty-block">读取失败：${error.message}</div>`;
  }
}

function renderDocuments(documents) {
  const counts = documents.reduce(
    (result, item) => {
      result.total += 1;
      if (item.published) result.published += 1;
      else result.draft += 1;
      if (item.status === "ocr_required") result.ocr += 1;
      return result;
    },
    { total: 0, draft: 0, published: 0, ocr: 0 },
  );
  document.querySelector("#documentTotal").textContent = counts.total;
  document.querySelector("#documentDraft").textContent = counts.draft;
  document.querySelector("#documentPublished").textContent = counts.published;
  document.querySelector("#documentOcr").textContent = counts.ocr;

  if (!documents.length) {
    documentList.innerHTML = `<div class="empty-block">还没有上传文档。</div>`;
    return;
  }
  documentList.innerHTML = "";
  documents.forEach((item) => {
    const isSystem = item.parse_method === "legacy_rag";
    const article = document.createElement("article");
    article.className = "document-card";
    article.innerHTML = `
      <div class="document-main">
        <div class="file-mark">${(item.filename.split(".").pop() || "F").toUpperCase()}</div>
        <div class="document-copy">
          <strong>${escapeHtml(item.filename)}</strong>
          <p>${formatBytes(item.size)} · ${escapeHtml(item.parse_method || "等待解析")} · ${formatDate(item.created_at)}</p>
          ${item.error ? `<small class="error-text">${escapeHtml(item.error)}</small>` : ""}
        </div>
      </div>
      <div class="document-actions">
        <span class="status-badge ${item.status}">${isSystem ? "系统导入" : STATUS_LABELS[item.status] || item.status}</span>
        <button type="button" data-action="preview" data-id="${item.id}">切片预览</button>
        <button type="button" data-action="ocr" data-id="${item.id}" ${["ocr_required", "ocr_pending"].includes(item.status) ? "" : "hidden"} ${item.status === "ocr_pending" ? "disabled" : ""}>${item.status === "ocr_pending" ? "OCR 中" : "运行 OCR"}</button>
        <button type="button" data-action="review-ocr" data-id="${item.id}" ${item.parse_method === "pdf_ocr" && item.status !== "ocr_pending" ? "" : "hidden"}>校对 OCR</button>
        <button type="button" data-action="publish" data-id="${item.id}" ${isSystem || item.status === "ocr_required" || item.status === "failed" ? "disabled" : ""}>发布</button>
        <button type="button" data-action="reprocess" data-id="${item.id}" ${isSystem ? "disabled" : ""}>重新处理</button>
        <button type="button" class="danger" data-action="delete" data-id="${item.id}" ${isSystem ? "disabled" : ""}>删除</button>
      </div>`;
    documentList.append(article);
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function uploadWithProgress(formData) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", "/api/documents/upload");
    request.upload.addEventListener("progress", (event) => {
      if (!event.lengthComputable) return;
      const percent = Math.round((event.loaded / event.total) * 100);
      uploadProgressBar.style.width = `${percent}%`;
      uploadProgressText.textContent = `正在上传 ${percent}%`;
    });
    request.addEventListener("load", () => {
      if (request.status >= 200 && request.status < 300) {
        resolve(JSON.parse(request.responseText));
      } else {
        let message = `HTTP ${request.status}`;
        try {
          message = JSON.parse(request.responseText).detail || message;
        } catch {}
        reject(new Error(message));
      }
    });
    request.addEventListener("error", () => reject(new Error("网络连接失败")));
    request.send(formData);
  });
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files[0];
  if (!file) {
    showToast("请先选择文件");
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  formData.append("strategy", document.querySelector("#chunkStrategy").value);
  formData.append("max_chars", document.querySelector("#maxChars").value);
  formData.append("overlap_chars", document.querySelector("#overlapChars").value);

  uploadButton.disabled = true;
  uploadProgress.hidden = false;
  uploadProgressBar.style.width = "0%";
  uploadProgressText.textContent = "正在上传";
  try {
    await uploadWithProgress(formData);
    showToast("文档已上传并生成预览");
    fileInput.value = "";
    setSelectedFile(null);
    await loadDocuments();
  } catch (error) {
    showToast(`上传失败：${error.message}`);
  } finally {
    uploadButton.disabled = false;
    uploadProgress.hidden = true;
  }
});

documentList.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const documentId = button.dataset.id;
  const action = button.dataset.action;
  button.disabled = true;
  try {
    if (action === "preview") {
      await previewDocument(documentId);
    } else if (action === "ocr") {
      button.textContent = "提交 OCR";
      const task = await apiAction(`/api/documents/${documentId}/ocr`, { method: "POST" });
      await watchOcrTask(task.id, documentId, button);
    } else if (action === "review-ocr") {
      await openOcrReview(documentId);
    } else if (action === "publish") {
      await apiAction(`/api/documents/${documentId}/publish`, { method: "POST" });
      showToast("文档已发布到检索库");
      await loadDocuments();
    } else if (action === "reprocess") {
      await apiAction(`/api/documents/${documentId}/reprocess`, { method: "POST" });
      showToast("已重新解析和切片");
      await loadDocuments();
    } else if (action === "delete") {
      if (!confirm("确定删除这份文档及其切片吗？")) return;
      await apiAction(`/api/documents/${documentId}`, { method: "DELETE" });
      showToast("文档已删除");
      await loadDocuments();
    }
  } catch (error) {
    showToast(`操作失败：${error.message}`);
  } finally {
    button.disabled = false;
  }
});

async function watchOcrTask(taskId, documentId, button) {
  while (true) {
    const task = await apiAction(`/api/tasks/${taskId}`);
    button.textContent = `OCR ${task.progress}%`;
    if (task.status === "completed") {
      showToast(task.message || "OCR 完成");
      await loadDocuments();
      await openOcrReview(documentId);
      return;
    }
    if (task.status === "failed") {
      showToast(`OCR 失败：${task.error || "未知错误"}`);
      await loadDocuments();
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

async function openOcrReview(documentId) {
  const pages = await apiAction(`/api/documents/${documentId}/ocr-pages`);
  currentOcrDocumentId = documentId;
  ocrDrawer.hidden = false;
  ocrDrawerTitle.textContent = "OCR 校对";
  const average = pages.length
    ? pages.reduce((sum, page) => sum + Number(page.confidence || 0), 0) / pages.length
    : 0;
  ocrDrawerMeta.textContent = `${pages.length} 页 · 平均置信度 ${(average * 100).toFixed(1)}%`;
  ocrPageList.innerHTML = "";
  pages.forEach((page) => {
    const section = document.createElement("section");
    section.className = "ocr-page";
    section.innerHTML = `
      <header>
        <strong>第 ${page.page_number} 页</strong>
        <span class="${Number(page.confidence) < 0.8 ? "low" : ""}">置信度 ${(Number(page.confidence || 0) * 100).toFixed(1)}%</span>
      </header>`;
    const textarea = document.createElement("textarea");
    textarea.dataset.pageNumber = page.page_number;
    textarea.value = page.text || "";
    section.append(textarea);
    ocrPageList.append(section);
  });
}

saveOcrPages.addEventListener("click", async () => {
  if (!currentOcrDocumentId) return;
  const pages = [...ocrPageList.querySelectorAll("textarea[data-page-number]")].map(
    (textarea) => ({
      page_number: Number(textarea.dataset.pageNumber),
      text: textarea.value,
      confidence: 0,
    }),
  );
  saveOcrPages.disabled = true;
  try {
    await apiAction(`/api/documents/${currentOcrDocumentId}/ocr-pages`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pages }),
    });
    showToast("OCR 校对已保存并重新切片");
    await loadDocuments();
  } catch (error) {
    showToast(`保存失败：${error.message}`);
  } finally {
    saveOcrPages.disabled = false;
  }
});

document.querySelector("#ocrDrawerClose").addEventListener("click", () => {
  ocrDrawer.hidden = true;
});

async function previewDocument(documentId) {
  const body = {
    strategy: document.querySelector("#chunkStrategy").value,
    max_chars: Number(document.querySelector("#maxChars").value),
    overlap_chars: Number(document.querySelector("#overlapChars").value),
  };
  const response = await authFetch(`/api/documents/${documentId}/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  chunkDrawer.hidden = false;
  chunkDrawerTitle.textContent = "切片预览";
  chunkDrawerMeta.textContent = `${data.chunks.length} 个切片 · ${data.strategy} · 最大 ${data.max_chars} 字`;
  chunkList.innerHTML = "";
  data.chunks.forEach((chunk, index) => {
    const article = document.createElement("article");
    article.className = "chunk-card";
    article.innerHTML = `
      <header><strong>${String(index + 1).padStart(2, "0")} ${escapeHtml(chunk.section || "")} ${escapeHtml(chunk.title || "")}</strong><span>第 ${chunk.page_start} 页</span></header>
      <p>${escapeHtml(chunk.content)}</p>
      <small>${escapeHtml(chunk.citation)}</small>`;
    chunkList.append(article);
  });
}

async function apiAction(url, options = {}) {
  const response = await authFetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}

document.querySelector("#chunkDrawerClose").addEventListener("click", () => {
  chunkDrawer.hidden = true;
});
document.querySelector("#refreshDocuments").addEventListener("click", loadDocuments);
loadDocuments();
