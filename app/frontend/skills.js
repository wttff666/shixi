const skillForm = document.querySelector("#skillForm");
const skillFile = document.querySelector("#skillFile");
const selectedSkillFile = document.querySelector("#selectedSkillFile");
const skillList = document.querySelector("#skillList");
const skillUploadButton = document.querySelector("#skillUploadButton");
const toast = document.querySelector("#toast");
const auth = requireAuth(["kb_admin", "sys_admin"]);
document.querySelector("#logoutButton")?.addEventListener("click", logout);
if (auth.user.role !== "sys_admin") {
  document.querySelectorAll("[data-sysadmin]").forEach((element) => {
    element.hidden = true;
  });
}

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

skillFile.addEventListener("change", () => {
  selectedSkillFile.textContent = skillFile.files[0]?.name || "尚未选择文件";
});

skillForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = skillFile.files[0];
  if (!file) {
    showToast("请先选择 Skill 文件");
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  skillUploadButton.disabled = true;
  try {
    const response = await authFetch("/api/skills/upload", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    showToast("Skill 已上传，当前为草稿状态");
    skillFile.value = "";
    selectedSkillFile.textContent = "尚未选择文件";
    await loadSkills();
  } catch (error) {
    showToast(`上传失败：${error.message}`);
  } finally {
    skillUploadButton.disabled = false;
  }
});

async function loadSkills() {
  skillList.innerHTML = `<div class="loading-block">正在读取 Skill...</div>`;
  try {
    const response = await authFetch("/api/skills");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    renderSkills(data);
  } catch (error) {
    skillList.innerHTML = `<div class="empty-block">读取失败：${escapeHtml(error.message)}</div>`;
  }
}

function renderSkills(skills) {
  if (!skills.length) {
    skillList.innerHTML = `<div class="empty-block">还没有上传 Skill。</div>`;
    return;
  }
  skillList.innerHTML = "";
  skills.forEach((skill) => {
    const article = document.createElement("article");
    article.className = "document-card skill-card";
    article.innerHTML = `
      <div class="document-main">
        <div class="file-mark">SK</div>
        <div class="document-copy">
          <strong>${escapeHtml(skill.name)}</strong>
          <p>${escapeHtml(skill.skill_id)} · v${escapeHtml(skill.version)}</p>
          <small>${escapeHtml(skill.description || "未填写说明")}</small>
        </div>
      </div>
      <div class="document-actions">
        <span class="status-badge ${skill.status}">${skill.status === "published" ? "已发布" : skill.status === "disabled" ? "已停用" : "草稿"}</span>
        <button type="button" data-action="publish" data-id="${escapeHtml(skill.skill_id)}" ${skill.status === "published" ? "disabled" : ""}>发布</button>
        <button type="button" data-action="disable" data-id="${escapeHtml(skill.skill_id)}" ${skill.status === "disabled" ? "disabled" : ""}>停用</button>
        <button type="button" class="danger" data-action="delete" data-id="${escapeHtml(skill.skill_id)}">删除</button>
      </div>`;
    skillList.append(article);
  });
}

skillList.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const action = button.dataset.action;
  const skillId = button.dataset.id;
  button.disabled = true;
  try {
    if (action === "delete") {
      if (!confirm("确定删除这个 Skill 吗？")) return;
      await authFetch(`/api/skills/${encodeURIComponent(skillId)}`, { method: "DELETE" });
      showToast("Skill 已删除");
    } else {
      await authFetch(`/api/skills/${encodeURIComponent(skillId)}/${action}`, { method: "POST" });
      showToast(action === "publish" ? "Skill 已发布" : "Skill 已停用");
    }
    await loadSkills();
  } catch (error) {
    showToast(`操作失败：${error.message}`);
  }
});

document.querySelector("#refreshSkills").addEventListener("click", loadSkills);
loadSkills();
