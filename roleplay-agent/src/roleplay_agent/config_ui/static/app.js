const state = { raw: null };

const recommended = {
  character: ["身份", "外貌", "心理内核", "允许临时变化", "禁止漂移", "备注"],
  persona: ["用户设定", "用户偏好", "关系备注"],
  events: ["当前事件"],
  lore: ["Lore"],
  memory: ["长期记忆"]
};

const lists = {
  character: document.getElementById("characterFields"),
  persona: document.getElementById("personaFields"),
  events: document.getElementById("eventFields"),
  lore: document.getElementById("loreFields"),
  memory: document.getElementById("memoryFields")
};

const advancedEditors = {
  app: document.getElementById("appEditor"),
  modelProfiles: document.getElementById("modelEditor"),
  qqBot: document.getElementById("qqEditor"),
  commands: document.getElementById("commandsEditor"),
  imageBridge: document.getElementById("imageBridgeEditor")
};

const promptEditors = {
  systemTemplate: document.getElementById("systemTemplateEditor"),
  dialogue_policy: document.getElementById("dialoguePolicyEditor"),
  session_profile: document.getElementById("sessionProfileEditor"),
  runtime_notes: document.getElementById("runtimeNotesEditor"),
  post_history_instructions: document.getElementById("postHistoryEditor")
};

const PREVIEW_USER_ID = "preview";
const statusText = document.getElementById("statusText");
const previewOutput = document.getElementById("previewOutput");
const pageTitle = document.getElementById("pageTitle");
const activeCharacterNameElement = document.getElementById("activeCharacterName");
const characterList = document.getElementById("characterList");
const nameModal = document.getElementById("nameModal");
const nameModalTitle = document.getElementById("nameModalTitle");
const nameModalInput = document.getElementById("nameModalInput");
const nameModalCancel = document.getElementById("nameModalCancel");
const nameModalConfirm = document.getElementById("nameModalConfirm");
const confirmModal = document.getElementById("confirmModal");
const confirmModalText = document.getElementById("confirmModalText");
const confirmModalCancel = document.getElementById("confirmModalCancel");
const confirmModalConfirm = document.getElementById("confirmModalConfirm");
const trashModal = document.getElementById("trashModal");
const trashList = document.getElementById("trashList");
const trashModalClose = document.getElementById("trashModalClose");
let pendingNameAction = null;
let pendingConfirmAction = null;

function activeUserId() {
  return PREVIEW_USER_ID;
}

function pretty(value) {
  return JSON.stringify(value ?? {}, null, 2);
}

function textFromValue(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item ?? "")).join("\n");
  }
  if (value && typeof value === "object") {
    return JSON.stringify(value, null, 2);
  }
  return String(value ?? "");
}

function makeId(label, index) {
  return String(label || `note_${index + 1}`)
    .trim()
    .replace(/\s+/g, "_")
    .replace(/[^\w\u4e00-\u9fa5-]/g, "_")
    || `note_${index + 1}`;
}

function createField(listName, label = "", content = "") {
  const template = document.getElementById("fieldTemplate");
  const node = template.content.firstElementChild.cloneNode(true);
  node.querySelector(".fieldName").value = label;
  node.querySelector(".fieldContent").value = content;
  node.querySelector(".removeFieldBtn").addEventListener("click", () => {
    node.remove();
    renderInsertPoints(listName);
  });
  lists[listName].appendChild(node);
  renderInsertPoints(listName);
  return node;
}

function clearList(listName) {
  lists[listName].replaceChildren();
}

function createInsertPoint(listName) {
  const point = document.createElement("button");
  point.className = "insertPoint";
  point.type = "button";
  point.setAttribute("aria-label", "新增");
  point.title = "新增";
  point.innerHTML = "<span>+</span>";
  point.addEventListener("click", () => {
    const node = createFieldNode(listName, "", "");
    lists[listName].insertBefore(node, point.nextSibling);
    renderInsertPoints(listName);
    node.querySelector(".fieldName").focus();
  });
  return point;
}

function createFieldNode(listName, label = "", content = "") {
  const template = document.getElementById("fieldTemplate");
  const node = template.content.firstElementChild.cloneNode(true);
  node.querySelector(".fieldName").value = label;
  node.querySelector(".fieldContent").value = content;
  node.querySelector(".removeFieldBtn").addEventListener("click", () => {
    node.remove();
    renderInsertPoints(listName);
  });
  return node;
}

function renderInsertPoints(listName) {
  const list = lists[listName];
  [...list.querySelectorAll(".insertPoint")].forEach((node) => node.remove());
  const fields = [...list.querySelectorAll(".dynamicField")];
  if (!fields.length) {
    list.appendChild(createInsertPoint(listName));
    return;
  }
  list.insertBefore(createInsertPoint(listName), fields[0]);
  fields.forEach((field) => {
    field.insertAdjacentElement("afterend", createInsertPoint(listName));
  });
}

function collectFields(listName) {
  return [...lists[listName].querySelectorAll(".dynamicField")]
    .map((node, index) => {
      const label = node.querySelector(".fieldName").value.trim();
      const content = node.querySelector(".fieldContent").value.trim();
      return label || content ? { id: makeId(label, index), label, content } : null;
    })
    .filter(Boolean);
}

function fillList(listName, fields) {
  clearList(listName);
  const resolved = fields.length ? fields : recommended[listName].map((label) => ({ label, content: "" }));
  resolved.forEach((field) => lists[listName].appendChild(createFieldNode(listName, field.label, field.content)));
  renderInsertPoints(listName);
}

function fieldsFromObject(payload, labelMap = {}) {
  if (!payload || typeof payload !== "object") return [];
  if (Array.isArray(payload.sections)) {
    return payload.sections.map((section) => ({
      label: String(section.title || section.label || section.id || ""),
      content: textFromValue(section.content)
    }));
  }
  if (Array.isArray(payload.fields)) {
    return payload.fields.map((field) => ({
      label: String(field.label || field.id || ""),
      content: textFromValue(field.content)
    }));
  }
  return Object.entries(payload)
    .filter(([key]) => !["schemaVersion", "id", "name", "metadata", "sourceProject", "sourceProfilePath", "displayName"].includes(key))
    .map(([key, value]) => ({ label: labelMap[key] || key, content: textFromValue(value) }))
    .filter((field) => field.content.trim());
}

function characterFields(character) {
  if (Array.isArray(character?.fields)) return fieldsFromObject(character);
  const subject = character?.subjectProfile || character?.roleplaySource || {};
  const editable = character?.editableRoleplay || {};
  return [
    ...fieldsFromObject(subject, {
      identity_zh: "身份",
      appearance_zh: "外貌",
      psychology_zh: "心理内核",
      allowed_changes_zh: "允许临时变化",
      forbidden_drift_zh: "禁止漂移",
      notes_zh: "备注"
    }),
    ...fieldsFromObject(editable)
  ];
}

function personaFields(persona) {
  if (Array.isArray(persona?.fields)) return fieldsFromObject(persona);
  return fieldsFromObject(persona, {
    profile: "用户设定",
    preferences: "用户偏好",
    relationshipNotes: "关系备注",
    editableNotes: "备注"
  });
}

function eventFields(eventsPayload) {
  const events = Array.isArray(eventsPayload?.events) ? eventsPayload.events : [];
  return events.map((event, index) => ({
    label: event.title || `事件 ${index + 1}`,
    content: textFromValue(event.content)
  }));
}

function loreFields(lorebook) {
  const entries = Array.isArray(lorebook?.entries) ? lorebook.entries : [];
  return entries.map((entry, index) => ({
    label: entry.label || entry.id || `Lore ${index + 1}`,
    content: textFromValue(entry.content)
  }));
}

function memoryFields(memory) {
  if (Array.isArray(memory?.fields)) return fieldsFromObject(memory);
  return fieldsFromObject(memory, { summary: "长期记忆" });
}

function parseAdvancedJson(name, element) {
  try {
    return JSON.parse(element.value || "{}");
  } catch (error) {
    throw new Error(`${name} 高级配置不是合法 JSON：${error.message}`);
  }
}

function fillAdvanced(data) {
  advancedEditors.app.value = pretty(data.app);
  advancedEditors.modelProfiles.value = pretty(data.modelProfiles);
  advancedEditors.qqBot.value = pretty(data.qqBot);
  advancedEditors.commands.value = pretty(data.commands);
  advancedEditors.imageBridge.value = pretty(data.imageBridge);
}

function activeCharacterId() {
  return String(state.raw?.characterCatalog?.activeCharacterId || "default");
}

function activeCharacterName() {
  const activeId = activeCharacterId();
  const items = Array.isArray(state.raw?.characterCatalog?.items) ? state.raw.characterCatalog.items : [];
  const item = items.find((entry) => String(entry.id) === activeId);
  return String(item?.name || state.raw?.character?.name || state.raw?.character?.displayName || activeId);
}

function renderActiveCharacterName() {
  if (activeCharacterNameElement) {
    activeCharacterNameElement.textContent = activeCharacterName();
  }
}

function renderCharacters(catalog) {
  characterList.replaceChildren();
  const items = Array.isArray(catalog?.items) ? catalog.items : [];
  const activeId = String(catalog?.activeCharacterId || "default");
  items.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `characterPill${String(item.id) === activeId ? " active" : ""}`;
    button.textContent = String(item.name || item.id || "角色");
    button.addEventListener("click", () => {
      activatePanel("character");
      if (String(item.id) !== activeId) {
        characterAction({ action: "select", characterId: item.id }).catch((error) => {
          statusText.textContent = error.message;
        });
      }
    });
    characterList.appendChild(button);
  });
  renderActiveCharacterName();
}

function openNameModal(title, initialValue, action) {
  pendingNameAction = action;
  nameModalTitle.textContent = title;
  nameModalInput.value = initialValue || "";
  nameModal.hidden = false;
  nameModalInput.focus();
  nameModalInput.select();
}

function closeNameModal() {
  pendingNameAction = null;
  nameModal.hidden = true;
}

function openConfirmModal(text, action) {
  pendingConfirmAction = action;
  confirmModalText.textContent = text;
  confirmModal.hidden = false;
  confirmModalConfirm.focus();
}

function closeConfirmModal() {
  pendingConfirmAction = null;
  confirmModal.hidden = true;
}

function renderTrash() {
  trashList.replaceChildren();
  const trash = Array.isArray(state.raw?.characterTrash) ? state.raw.characterTrash : [];
  if (!trash.length) {
    const empty = document.createElement("div");
    empty.className = "trashEmpty";
    empty.textContent = "空";
    trashList.appendChild(empty);
    return;
  }
  trash.forEach((item) => {
    const row = document.createElement("div");
    row.className = "trashRow";
    const name = document.createElement("span");
    name.textContent = String(item.name || item.id || "角色");
    const actions = document.createElement("div");
    actions.className = "trashActions";
    const restore = document.createElement("button");
    restore.type = "button";
    restore.textContent = "恢复";
    restore.addEventListener("click", () => {
      characterAction({ action: "restore", characterId: item.id }).then(() => {
        renderTrash();
      }).catch((error) => { statusText.textContent = error.message; });
    });
    const purge = document.createElement("button");
    purge.type = "button";
    purge.className = "secondary";
    purge.textContent = "彻底删除";
    purge.addEventListener("click", () => {
      characterAction({ action: "purge", characterId: item.id }).then(() => {
        renderTrash();
      }).catch((error) => { statusText.textContent = error.message; });
    });
    actions.append(restore, purge);
    row.append(name, actions);
    trashList.appendChild(row);
  });
}

function openTrashModal() {
  renderTrash();
  trashModal.hidden = false;
}

function closeTrashModal() {
  trashModal.hidden = true;
}

async function characterAction(payload) {
  statusText.textContent = "正在保存";
  const response = await fetch("/api/characters", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.error || "保存失败");
  state.raw = {
    ...(state.raw || {}),
    characterCatalog: data.characterCatalog,
    characterTrash: data.characterTrash,
    character: data.character
  };
  renderCharacters(data.characterCatalog);
  fillList("character", characterFields(data.character || {}));
  renderActiveCharacterName();
  statusText.textContent = "";
}

function buildCharacterPayload() {
  const previous = state.raw?.character || {};
  return {
    schemaVersion: previous.schemaVersion || 1,
    id: previous.id || activeCharacterId(),
    name: previous.name || previous.displayName || activeCharacterName(),
    sections: collectFields("character").map((field) => ({
      id: field.id,
      title: field.label,
      content: field.content
    })),
    metadata: previous.metadata || {}
  };
}

function buildPersonaPayload() {
  return {
    id: state.raw?.persona?.id || "default",
    displayName: state.raw?.persona?.displayName || "用户",
    fields: collectFields("persona")
  };
}

function buildEventsPayload() {
  return {
    events: collectFields("events").map((field, index) => ({
      id: field.id || `event_${index + 1}`,
      enabled: true,
      title: field.label,
      content: field.content,
      priority: 100 - index
    }))
  };
}

function buildLorebookPayload() {
  return {
    entries: collectFields("lore").map((field, index) => ({
      id: field.id || `lore_${index + 1}`,
      label: field.label,
      enabled: true,
      alwaysActive: true,
      keys: [],
      order: index + 1,
      content: field.content
    }))
  };
}

function buildMemoryPayload() {
  return {
    ...(state.raw?.memory || {}),
    fields: collectFields("memory")
  };
}

async function loadConfig() {
  statusText.textContent = "";
  const response = await fetch(`/api/config?userId=${encodeURIComponent(activeUserId())}`);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "加载失败");
  state.raw = data;
  renderCharacters(data.characterCatalog || {});
  state.raw.characterTrash = data.characterTrash || [];
  fillList("character", characterFields(data.character || {}));
  fillList("persona", personaFields(data.persona || {}));
  fillList("events", eventFields(data.events || {}));
  fillList("lore", loreFields(data.lorebook || {}));
  fillList("memory", memoryFields(data.memory || {}));
  fillAdvanced(data);
  for (const [key, editor] of Object.entries(promptEditors)) {
    editor.value = data.prompts?.[key] ?? "";
  }
  statusText.textContent = "";
}

async function saveConfig() {
  statusText.textContent = "";
  const payload = {
    app: parseAdvancedJson("应用配置", advancedEditors.app),
    modelProfiles: parseAdvancedJson("模型档案", advancedEditors.modelProfiles),
    qqBot: parseAdvancedJson("QQ 出口", advancedEditors.qqBot),
    commands: parseAdvancedJson("指令词", advancedEditors.commands),
    imageBridge: parseAdvancedJson("生图桥接", advancedEditors.imageBridge),
    character: buildCharacterPayload(),
    persona: buildPersonaPayload(),
    events: buildEventsPayload(),
    lorebook: buildLorebookPayload(),
    memory: buildMemoryPayload(),
    prompts: {}
  };
  for (const [key, editor] of Object.entries(promptEditors)) {
    payload.prompts[key] = editor.value;
  }
  const response = await fetch(`/api/config?userId=${encodeURIComponent(activeUserId())}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.error || "保存失败");
  if (data.characterCatalog) {
    state.raw.characterCatalog = data.characterCatalog;
    renderCharacters(data.characterCatalog);
  }
  if (data.characterTrash) {
    state.raw.characterTrash = data.characterTrash;
  }
  renderActiveCharacterName();
  statusText.textContent = "";
  await loadConfig();
}

async function previewPrompt() {
  previewOutput.textContent = "生成中";
  const response = await fetch("/api/prompt-preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      userId: activeUserId(),
      userText: document.getElementById("previewUserText").value
    })
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "预览失败");
  previewOutput.textContent = pretty(data);
}

function activatePanel(name) {
  document.querySelectorAll(".tab").forEach((item) => item.classList.toggle("active", item.dataset.tab === name));
  document.querySelectorAll(".panel").forEach((panel) => {
    const active = panel.dataset.panel === name;
    panel.classList.toggle("active", active);
    if (active && pageTitle) {
      pageTitle.textContent = panel.dataset.title || "";
    }
  });
}

function bindTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      activatePanel(tab.dataset.tab);
    });
  });
}

function bindActions() {
  document.getElementById("reloadBtn").addEventListener("click", () => {
    loadConfig().catch((error) => { statusText.textContent = error.message; });
  });
  document.getElementById("saveBtn").addEventListener("click", () => {
    saveConfig().catch((error) => { statusText.textContent = error.message; });
  });
  document.getElementById("previewBtn").addEventListener("click", () => {
    previewPrompt().catch((error) => { previewOutput.textContent = error.message; });
  });
  document.getElementById("createCharacterBtn").addEventListener("click", () => {
    openNameModal("新建角色", "", (name) => characterAction({ action: "create", name }));
  });
  document.getElementById("duplicateCharacterBtn").addEventListener("click", () => {
    openNameModal("复制角色", `${activeCharacterName()} 副本`, (name) => characterAction({ action: "duplicate", characterId: activeCharacterId(), name }));
  });
  document.getElementById("renameCharacterBtn").addEventListener("click", () => {
    openNameModal("重命名角色", activeCharacterName(), (name) => characterAction({ action: "rename", characterId: activeCharacterId(), name }));
  });
  document.getElementById("deleteCharacterBtn").addEventListener("click", () => {
    openConfirmModal(`删除「${activeCharacterName()}」？`, () => characterAction({ action: "delete", characterId: activeCharacterId() }));
  });
  document.getElementById("trashCharacterBtn").addEventListener("click", openTrashModal);
  nameModalCancel.addEventListener("click", closeNameModal);
  nameModal.addEventListener("click", (event) => {
    if (event.target === nameModal) closeNameModal();
  });
  nameModalConfirm.addEventListener("click", () => {
    const name = nameModalInput.value.trim();
    if (!name || !pendingNameAction) return;
    const action = pendingNameAction;
    closeNameModal();
    action(name).catch((error) => { statusText.textContent = error.message; });
  });
  nameModalInput.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeNameModal();
    if (event.key === "Enter") nameModalConfirm.click();
  });
  confirmModalCancel.addEventListener("click", closeConfirmModal);
  confirmModal.addEventListener("click", (event) => {
    if (event.target === confirmModal) closeConfirmModal();
  });
  confirmModalConfirm.addEventListener("click", () => {
    if (!pendingConfirmAction) return;
    const action = pendingConfirmAction;
    closeConfirmModal();
    action().catch((error) => { statusText.textContent = error.message; });
  });
  trashModalClose.addEventListener("click", closeTrashModal);
  trashModal.addEventListener("click", (event) => {
    if (event.target === trashModal) closeTrashModal();
  });
}

bindTabs();
bindActions();
loadConfig().catch((error) => { statusText.textContent = error.message; });
