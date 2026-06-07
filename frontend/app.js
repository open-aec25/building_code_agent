const API_BASE_KEY = "windLoadApiBase";
const SESSION_KEY = "windLoadSessionId";
const TTS_MUTED_KEY = "windLoadTtsMuted";
const LLM_ENABLED_KEY = "windLoadLlmEnabled";

const DEFAULT_API_BASE = "http://127.0.0.1:8000";
const urlParams = new URLSearchParams(window.location.search);
const configuredApiBase = urlParams.get("apiBase") || urlParams.get("api");
if (configuredApiBase) {
  sessionStorage.setItem(API_BASE_KEY, configuredApiBase.replace(/\/$/, ""));
}
const PHASE_NAMES = {
  1: "Building classification",
  2: "Site and wind speed",
  3: "Exposure category",
  4: "Topographic feature",
  5: "Building geometry",
  6: "Design intent",
  7: "Confirmation and results",
};

const state = {
  apiBase: sessionStorage.getItem(API_BASE_KEY) || DEFAULT_API_BASE,
  sessionId: sessionStorage.getItem(SESSION_KEY),
  sessionState: null,
  messages: [],
  loading: false,
  ttsMuted: localStorage.getItem(TTS_MUTED_KEY) === "true",
  ttsAvailable: true,
  llmEnabled: localStorage.getItem(LLM_ENABLED_KEY) === "true",
  llmAvailable: true,
  audioUrl: null,
};

const els = {
  messageList: document.querySelector("#messageList"),
  chatForm: document.querySelector("#chatForm"),
  messageInput: document.querySelector("#messageInput"),
  sendButton: document.querySelector("#sendButton"),
  newSessionButton: document.querySelector("#newSessionButton"),
  phaseLabel: document.querySelector("#phaseLabel"),
  flowState: document.querySelector("#flowState"),
  progressFill: document.querySelector("#progressFill"),
  connectionStatus: document.querySelector("#connectionStatus"),
  ttsToggle: document.querySelector("#ttsToggle"),
  ttsIcon: document.querySelector("#ttsIcon"),
  llmToggle: document.querySelector("#llmToggle"),
  llmIcon: document.querySelector("#llmIcon"),
  ttsAudio: document.querySelector("#ttsAudio"),
  refreshResultsButton: document.querySelector("#refreshResultsButton"),
  resultsEmpty: document.querySelector("#resultsEmpty"),
  resultsContent: document.querySelector("#resultsContent"),
};

document.addEventListener("DOMContentLoaded", init);

function init() {
  els.chatForm.addEventListener("submit", handleSubmit);
  els.newSessionButton.addEventListener("click", () => createSession(true));
  els.refreshResultsButton.addEventListener("click", renderLatestResults);
  els.ttsToggle.addEventListener("click", toggleTts);
  els.llmToggle.addEventListener("click", toggleLlm);
  els.messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      els.chatForm.requestSubmit();
    }
  });

  updateTtsButton();
  updateLlmButton();
  loadRuntimeStatus();
  hydrateSession();
}

async function loadRuntimeStatus() {
  try {
    const health = await apiFetch("/health");
    state.llmAvailable = Boolean(health.llm?.request_toggle_available);
    if (!state.llmAvailable && state.llmEnabled) {
      state.llmEnabled = false;
      localStorage.setItem(LLM_ENABLED_KEY, "false");
      setStatus("Anthropic LLM is unavailable because the backend does not have an API key configured.");
    }
    updateLlmButton();
  } catch (error) {
    state.llmAvailable = false;
    updateLlmButton();
  }
}

async function hydrateSession() {
  if (!state.sessionId) {
    await createSession(false);
    return;
  }

  try {
    const session = await apiFetch(`/session/${state.sessionId}/state`);
    state.sessionState = session;
    state.messages = session.messages || [];
    renderMessages();
    updateFlow(session);
    await renderLatestResults();
  } catch (error) {
    setStatus("Starting a fresh session because the previous one is no longer available.");
    await createSession(false);
  }
}

async function createSession(userInitiated) {
  setLoading(true);
  try {
    const body = await apiFetch("/session/new", { method: "POST" });
    state.sessionId = body.session_id;
    state.sessionState = body.session_state;
    state.messages = [];
    sessionStorage.setItem(SESSION_KEY, state.sessionId);
    clearResults();
    renderMessages();
    updateFlow(state.sessionState);
    addLocalAssistantMessage("What is the primary use of this building? For example: office, warehouse, retail, school, hospital, or residential.");
    setStatus(userInitiated ? "New session ready." : "Session ready.");
    els.messageInput.focus();
  } catch (error) {
    setStatus(`Could not create a backend session. Check that FastAPI is running at ${state.apiBase}.`);
  } finally {
    setLoading(false);
  }
}

async function handleSubmit(event) {
  event.preventDefault();
  const message = els.messageInput.value.trim();
  if (!message || state.loading || !state.sessionId) return;

  els.messageInput.value = "";
  pushMessage("user", message);
  setLoading(true);
  setStatus("Waiting for backend response...");

  try {
    const body = await apiFetch(`/session/${state.sessionId}/message`, {
      method: "POST",
      body: JSON.stringify({ message, llm_enabled: state.llmEnabled }),
    });
    state.sessionState = body.session_state;
    state.messages = body.session_state.messages || state.messages;
    renderMessages();
    updateFlow(body.session_state);
    setStatus(llmTurnStatus(body));

    const assistantBubble = lastAssistantBubble();
    if (body.spoken_text) {
      playTts(body.spoken_text, assistantBubble);
    }
    if (body.session_state?.current_question_id === "COMPLETE") {
      await renderLatestResults();
    }
  } catch (error) {
    pushMessage("assistant", error.message || "The backend request failed.");
    setStatus("Request failed. The conversation state was not updated.");
  } finally {
    setLoading(false);
    els.messageInput.focus();
  }
}

async function renderLatestResults() {
  if (!state.sessionState?.collected_inputs || state.sessionState.current_question_id !== "COMPLETE") {
    els.refreshResultsButton.disabled = true;
    return;
  }

  els.refreshResultsButton.disabled = false;
  els.refreshResultsButton.textContent = "Refreshing...";
  try {
    const body = await apiFetch(`/session/${state.sessionId}/calculate`, {
      method: "POST",
      body: JSON.stringify(state.sessionState.collected_inputs),
    });
    state.sessionState = body.session_state;
    renderFormattedDisplay(body.formatted_display, body.formatted_markdown);
  } catch (error) {
    setStatus(`Results refresh failed: ${error.message}`);
  } finally {
    els.refreshResultsButton.textContent = "Refresh";
  }
}

async function playTts(text, bubble) {
  if (state.ttsMuted || !state.ttsAvailable) return;

  try {
    bubble?.classList.add("speaking");
    const response = await fetch(`${state.apiBase}/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, session_id: state.sessionId }),
    });

    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const payload = await response.json();
      if (payload.tts_available === false) {
        state.ttsAvailable = false;
        updateTtsButton();
      }
      return;
    }
    if (!response.ok) throw new Error(`TTS failed with HTTP ${response.status}`);

    const blob = await response.blob();
    if (state.audioUrl) URL.revokeObjectURL(state.audioUrl);
    state.audioUrl = URL.createObjectURL(blob);
    els.ttsAudio.src = state.audioUrl;
    await els.ttsAudio.play();
  } catch (error) {
    setStatus("Voice playback is unavailable for this turn.");
  } finally {
    bubble?.classList.remove("speaking");
  }
}

function renderFormattedDisplay(display, markdown) {
  els.resultsEmpty.hidden = true;
  els.resultsContent.hidden = false;
  els.resultsContent.replaceChildren();

  const summary = display.project_summary || {};
  els.resultsContent.append(
    section("Key Summary", keyValueGrid(summary)),
    section("Velocity Pressure", keyValueGrid(display.velocity_pressure || {})),
    section("User Inputs", keyValueGrid(display.user_inputs || {})),
    section("Derived Ratios", keyValueGrid(display.derived_ratios || {})),
    section("Wall Pressures", table(["Surface", "Height", "Cp", "+GCpi calculated psf", "-GCpi calculated psf", "Minimum"], display.wall_pressures || [])),
    section("Roof Pressures", table(["Zone/Surface", "Cp", "Area ft2", "+GCpi calculated psf", "-GCpi calculated psf", "Minimum"], display.roof_pressures || [])),
    section("Wind Direction Cases", table(["Wind", "Along depth ft", "Transverse width ft", "h/L", "L/B", "+GCpi horizontal kips", "-GCpi horizontal kips", "Max calculated horizontal kips", "Minimum horizontal kips", "Governing horizontal kips"], display.wind_direction_cases || [])),
    section("Assumptions and Defaults", objectTable(["Parameter", "Value", "Reference", "Note"], display.assumptions_defaults || [])),
    section("Minimum Checks", table(["Surface", "Case", "Value psf", "Minimum psf", "Controlled", "Reference"], display.minimum_pressure_checks || [])),
    section("Warnings and References", listBlock([...(display.warnings_limitations || []), ...(display.references || [])]))
  );

  if (markdown) {
    const details = document.createElement("details");
    details.className = "markdown-report";
    details.innerHTML = `<summary>Markdown report</summary><pre></pre>`;
    details.querySelector("pre").textContent = markdown;
    els.resultsContent.append(details);
  }
}

function section(title, content) {
  const node = document.createElement("section");
  node.className = "result-section";
  const heading = document.createElement("h3");
  heading.textContent = title;
  node.append(heading, content);
  return node;
}

function keyValueGrid(values) {
  const grid = document.createElement("dl");
  grid.className = "kv-grid";
  Object.entries(values).forEach(([key, value]) => {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = labelize(key);
    dd.textContent = formatValue(value);
    grid.append(dt, dd);
  });
  return grid;
}

function objectTable(headers, rows) {
  return table(headers, rows.map((row) => headers.map((header) => row[header.toLowerCase()] ?? row[toSnake(header)] ?? "")));
}

function table(headers, rows) {
  const wrapper = document.createElement("div");
  wrapper.className = "table-wrap";
  const tableNode = document.createElement("table");
  const thead = document.createElement("thead");
  const tr = document.createElement("tr");
  headers.forEach((header) => {
    const th = document.createElement("th");
    th.textContent = header;
    tr.append(th);
  });
  thead.append(tr);
  const tbody = document.createElement("tbody");
  rows.forEach((row) => {
    const bodyRow = document.createElement("tr");
    row.forEach((cell) => {
      const td = document.createElement("td");
      td.textContent = formatValue(cell);
      if (cell === true || String(cell).includes("+GCpi") || String(cell).includes("-GCpi")) {
        td.classList.add("controlled");
      }
      bodyRow.append(td);
    });
    tbody.append(bodyRow);
  });
  if (!rows.length) {
    const emptyRow = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = headers.length;
    td.textContent = "No rows returned.";
    emptyRow.append(td);
    tbody.append(emptyRow);
  }
  tableNode.append(thead, tbody);
  wrapper.append(tableNode);
  return wrapper;
}

function listBlock(items) {
  const list = document.createElement("ul");
  list.className = "plain-list";
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    list.append(li);
  });
  return list;
}

function renderMessages() {
  els.messageList.replaceChildren();
  state.messages.forEach((message) => appendBubble(message.role, message.content));
  scrollMessages();
}

function pushMessage(role, content) {
  state.messages.push({ role, content });
  appendBubble(role, content);
  scrollMessages();
}

function addLocalAssistantMessage(content) {
  if (state.messages.length) return;
  pushMessage("assistant", content);
}

function appendBubble(role, content) {
  const bubble = document.createElement("article");
  bubble.className = `message ${role === "user" ? "user-message" : "assistant-message"}`;
  const label = document.createElement("span");
  label.className = "message-role";
  label.textContent = role === "user" ? "You" : "Assistant";
  const body = document.createElement("div");
  body.className = "message-body";
  body.textContent = content;
  bubble.append(label, body);
  els.messageList.append(bubble);
}

function lastAssistantBubble() {
  return [...els.messageList.querySelectorAll(".assistant-message")].at(-1);
}

function updateFlow(session) {
  const phase = Number(session?.current_phase || 1);
  const question = session?.current_question_id || "Q1";
  els.phaseLabel.textContent = `Phase ${phase} of 7 - ${PHASE_NAMES[phase] || "Conversation"}`;
  els.progressFill.style.width = `${Math.max(1, Math.min(7, phase)) / 7 * 100}%`;

  if (question === "COMPLETE") {
    els.flowState.textContent = "Finished";
  } else if (question === "CONFIRM" || session?.ready_to_calculate) {
    els.flowState.textContent = "Ready to confirm";
  } else {
    els.flowState.textContent = "Collecting inputs";
  }
}

function setLoading(isLoading) {
  state.loading = isLoading;
  els.sendButton.disabled = isLoading;
  els.messageInput.disabled = isLoading;
  els.newSessionButton.disabled = isLoading;
  els.sendButton.textContent = isLoading ? "Sending..." : "Send";
}

function clearResults() {
  els.resultsContent.replaceChildren();
  els.resultsContent.hidden = true;
  els.resultsEmpty.hidden = false;
  els.refreshResultsButton.disabled = true;
}

function toggleTts() {
  state.ttsMuted = !state.ttsMuted;
  localStorage.setItem(TTS_MUTED_KEY, String(state.ttsMuted));
  updateTtsButton();
}

function toggleLlm() {
  if (!state.llmAvailable) {
    setStatus("Anthropic LLM is unavailable until ANTHROPIC_API_KEY is configured on the backend.");
    return;
  }
  state.llmEnabled = !state.llmEnabled;
  localStorage.setItem(LLM_ENABLED_KEY, String(state.llmEnabled));
  updateLlmButton();
  setStatus(state.llmEnabled ? "Anthropic LLM assistance is on for future messages." : "Deterministic-only mode is on for future messages.");
}

function updateTtsButton() {
  els.ttsToggle.hidden = !state.ttsAvailable;
  els.ttsToggle.classList.toggle("muted", state.ttsMuted);
  els.ttsIcon.textContent = state.ttsMuted ? "Voice off" : "Voice on";
}

function updateLlmButton() {
  els.llmToggle.disabled = !state.llmAvailable;
  els.llmToggle.classList.toggle("muted", !state.llmEnabled);
  els.llmToggle.classList.toggle("enabled", state.llmEnabled);
  els.llmIcon.textContent = state.llmAvailable
    ? state.llmEnabled ? "LLM on" : "LLM off"
    : "LLM unavailable";
}

function llmTurnStatus(body) {
  if (body.llm_used) return "Anthropic LLM assisted this response.";
  if (state.llmEnabled && body.llm_fallback_reason) {
    return `Deterministic fallback used. LLM reason: ${body.llm_fallback_reason}.`;
  }
  return "";
}

function setStatus(message) {
  els.connectionStatus.textContent = message;
}

async function apiFetch(path, options = {}) {
  const response = await fetch(`${state.apiBase}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = body?.detail || body || `HTTP ${response.status}`;
    throw new Error(Array.isArray(detail) ? detail.map((item) => item.msg).join("; ") : detail);
  }
  return body;
}

function scrollMessages() {
  els.messageList.scrollTop = els.messageList.scrollHeight;
}

function labelize(key) {
  return key.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function toSnake(label) {
  return label.toLowerCase().replaceAll(" ", "_").replaceAll("/", "_");
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
