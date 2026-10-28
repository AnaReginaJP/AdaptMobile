/**
 * AdaptMobile — Single Page Application Logic
 */

// Application State
const REGION_LABELS = { mx: "México", us: "EE. UU.", ca: "Canadá" };
const savedRegion = localStorage.getItem("adaptmobile_region");

const state = {
  region: REGION_LABELS[savedRegion] ? savedRegion : "mx",
  token: localStorage.getItem("adaptmobile_token") || null,
  user: null,
  currentAnalysis: null,
  currentAnalysisId: null,
  activeTab: "analyzer",
  deviceFilter: {
    status: "",
    brand: "",
    search: "",
    skip: 0,
    limit: 50,
    total: 0
  },
  catalogFilter: {
    brand: "",
    os: "",
    search: "",
    skip: 0,
    limit: 50,
    total: 0
  }
};

const API_BASE = "/api";

function regionLabel(r) {
  return REGION_LABELS[r] || REGION_LABELS.mx;
}

function updateRegionButtons() {
  document.querySelectorAll(".region-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.region === state.region);
  });
}

// Cambia el mercado (México / EE. UU. / Canadá): recarga marcas y catálogo
function setRegion(region) {
  if (!REGION_LABELS[region] || region === state.region) return;
  state.region = region;
  localStorage.setItem("adaptmobile_region", region);
  state.deviceFilter.brand = "";
  state.catalogFilter.brand = "";
  state.catalogFilter.skip = 0;
  updateRegionButtons();
  loadBrandFilters();
  if (state.activeTab === "devices") loadCatalogDevices();
}

// Sample Demo Files content
const DEMO_FILES = {
  "react-native": {
    filename: "package.json",
    content: JSON.stringify({
      name: "cyber-ar-store",
      version: "1.0.0",
      dependencies: {
        "react": "18.2.0",
        "react-native": "0.74.1",
        "@react-three/fiber": "^8.16.0",
        "three": "^0.164.0",
        "react-native-vision-camera": "^4.0.0",
        "@tensorflow/tfjs-react-native": "^0.8.0",
        "@react-navigation/native": "^6.1.0"
      }
    }, null, 2)
  },
  "flutter": {
    filename: "pubspec.yaml",
    content: `name: flutter_vision_flow
description: A high-performance Flutter mobile application.
version: 1.0.0+1
environment:
  sdk: ">=3.0.0 <4.0.0"
dependencies:
  flutter:
    sdk: flutter
  camera: ^0.10.5
  tflite_flutter: ^0.10.4
  video_player: ^2.8.2
  dio: ^5.4.0
  provider: ^6.1.1`
  },
  "android-gradle": {
    filename: "build.gradle.kts",
    content: `plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.compose.compiler)
}

android {
    namespace = "com.adaptmobile.nativeapp"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.adaptmobile.nativeapp"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }

    dependencies {
        implementation(libs.androidx.compose.ui)
        implementation("androidx.camera:camera-camera2:1.3.1")
        implementation("org.tensorflow:tensorflow-lite:2.14.0")
        implementation("androidx.media3:media3-exoplayer:1.2.0")
    }
}`
  },
  "unity": {
    filename: "README.md",
    content: `# CyberStrike Mobile (Unity 3D Engine)

Mobile AAA Shooter built with Unity 2023.2 LTS and Universal Render Pipeline (URP).

## Technical Requirements
- Target: Android and iOS
- Graphics: Vulkan 1.1 / Metal 2.0 with ASTC Texture Compression
- Target 60 FPS on modern mobile chipsets
- Real-time shadows, post-processing bloom, and PBR shaders.`
  }
};

// ==========================================
// INITIALIZATION
// ==========================================
document.addEventListener("DOMContentLoaded", async () => {
  setupDropZone();
  setupEventListeners();
  updateRegionButtons();
  loadBrandFilters();

  if (state.token) {
    await fetchCurrentUser();
  } else {
    updateAuthUI();
  }
});

// ==========================================
// AUTHENTICATION
// ==========================================
async function fetchCurrentUser() {
  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: { "Authorization": `Bearer ${state.token}` }
    });
    if (res.ok) {
      state.user = await res.json();
      updateAuthUI();
    } else {
      handleLogout();
    }
  } catch (err) {
    console.error("Auth check failed:", err);
    handleLogout();
  }
}

// ==========================================
// EMBUDO DE CONVERSIÓN Y AVISO DE CRÉDITOS
// ==========================================
const FUNNEL_LABELS = {
  register: "Registro",
  upload_started: "Subida iniciada",
  analysis_done: "Análisis completado",
  limit_reached: "Límite alcanzado",
  pricing_viewed: "Vio los planes",
  upgrade_clicked: "Clic en mejorar plan"
};

// Telemetría ligera: nunca bloquea la UX ni rompe nada si falla.
function trackEvent(event) {
  if (!state.token) return;
  fetch(`${API_BASE}/events`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${state.token}`
    },
    body: JSON.stringify({ event })
  }).catch(() => {});
}

// El backend puede devolver detail como texto o como objeto {code, message}
function errorMessage(data, fallback) {
  const detail = data && data.detail;
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  return detail.message || fallback;
}

function showCreditsAlert(show) {
  const alertBox = document.getElementById("credits-alert");
  if (!alertBox) return;
  alertBox.style.display = show ? "flex" : "none";
}

function updateAuthUI() {
  const unlogged = document.getElementById("auth-unlogged");
  const logged = document.getElementById("auth-logged");
  const adminNav = document.getElementById("nav-admin");

  if (state.user) {
    unlogged.style.display = "none";
    logged.style.display = "flex";

    document.getElementById("user-email").textContent = state.user.email;
    document.getElementById("user-avatar").textContent = state.user.email[0].toUpperCase();
    document.getElementById("user-role-badge").textContent = state.user.plan.toUpperCase();

    // Credits counter
    const creditsPill = document.getElementById("credits-pill");
    const creditsText = document.getElementById("credits-text");
    if (state.user.role === "admin") {
      creditsText.textContent = "Admin (Ilimitado)";
    } else {
      const remaining = Math.max(0, state.user.credits_limit - state.user.credits_used);
      creditsText.textContent = `Créditos: ${remaining}/${state.user.credits_limit}`;
      if (remaining === 0) {
        creditsPill.style.borderColor = "var(--accent-rose)";
        creditsPill.style.color = "var(--accent-rose)";
      }
      showCreditsAlert(remaining === 0);   // aviso persistente con enlace a planes
    }

    if (state.user.role === "admin") {
      adminNav.style.display = "flex";
    } else {
      adminNav.style.display = "none";
    }
  } else {
    unlogged.style.display = "flex";
    logged.style.display = "none";
    adminNav.style.display = "none";
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const email = document.getElementById("login-email").value;
  const password = document.getElementById("login-password").value;

  try {
    const res = await fetch(`${API_BASE}/auth/login-json`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Error al iniciar sesión");

    state.token = data.access_token;
    state.user = data.user;
    localStorage.setItem("adaptmobile_token", state.token);
    updateAuthUI();
    closeAuthModal();
    showToast("Sesión iniciada con éxito", "success");
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function handleRegister(e) {
  e.preventDefault();
  const full_name = document.getElementById("reg-name").value;
  const email = document.getElementById("reg-email").value;
  const password = document.getElementById("reg-password").value;

  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ full_name, email, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Error al registrarse");

    state.token = data.access_token;
    state.user = data.user;
    localStorage.setItem("adaptmobile_token", state.token);
    updateAuthUI();
    closeAuthModal();
    showToast("Cuenta creada con Plan Gratuito (2 créditos)", "success");
    trackEvent("register");
  } catch (err) {
    showToast(err.message, "error");
  }
}

function handleLogout() {
  state.token = null;
  state.user = null;
  localStorage.removeItem("adaptmobile_token");
  updateAuthUI();
  document.getElementById("user-dropdown").classList.remove("open");
  showToast("Sesión cerrada", "info");
}

function fillAdminCredentials() {
  document.getElementById("login-email").value = "admin@adaptmobile.io";
  document.getElementById("login-password").value = "admin123";
}

// ==========================================
// NAVIGATION & TABS
// ==========================================
function switchTab(tabName) {
  state.activeTab = tabName;
  document.querySelectorAll(".view-section").forEach(sec => sec.style.display = "none");
  document.querySelectorAll(".nav-btn").forEach(btn => btn.classList.remove("active"));

  const targetSec = document.getElementById(`view-${tabName}`);
  const targetBtn = document.getElementById(`nav-${tabName}`);
  if (targetSec) targetSec.style.display = "block";
  if (targetBtn) targetBtn.classList.add("active");

  if (tabName === "history") {
    loadUserHistory();
  } else if (tabName === "devices") {
    loadCatalogDevices();
  } else if (tabName === "admin") {
    loadAdminStats();
  }
}

function toggleUserDropdown() {
  const dd = document.getElementById("user-dropdown");
  dd.classList.toggle("open");
}

// ==========================================
// FILE UPLOAD & DROPZONE
// ==========================================
function setupDropZone() {
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("drag-over");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    if (e.dataTransfer.files.length > 0) {
      uploadFile(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      uploadFile(e.target.files[0]);
    }
  });
}

function loadDemoProject(demoKey) {
  const demo = DEMO_FILES[demoKey];
  if (!demo) return;

  const file = new File([demo.content], demo.filename, { type: "text/plain" });
  uploadFile(file);
}

async function uploadFile(file) {
  if (!state.token) {
    openAuthModal("login");
    showToast("Inicia sesión para realizar un análisis de compatibilidad", "info");
    return;
  }

  // Check client-side credits
  if (state.user && state.user.role !== "admin" && state.user.credits_used >= state.user.credits_limit) {
    openPlansModal();
    showCreditsAlert(true);
    trackEvent("limit_reached");
    showToast(`Has agotado tus ${state.user.credits_limit} análisis del mes. Mejora tu plan para continuar.`, "error");
    return;
  }

  trackEvent("upload_started");

  const loading = document.getElementById("analysis-loading");
  const loadingText = document.getElementById("loading-step-text");
  loading.style.display = "block";
  loadingText.textContent = `Analizando ${file.name}...`;

  const formData = new FormData();
  formData.append("file", file);
  formData.append("region", state.region);

  try {
    loadingText.textContent = "IA estimando requerimientos de hardware...";
    const res = await fetch(`${API_BASE}/analysis/upload`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${state.token}` },
      body: formData
    });

    const data = await res.json();
    if (!res.ok) {
      if (res.status === 402) {
        // Límite agotado: código identificable 'credits_exhausted' desde el backend
        openPlansModal();
        showCreditsAlert(true);
      }
      throw new Error(errorMessage(data, "Error en el análisis"));
    }

    state.currentAnalysis = data;
    state.currentAnalysisId = data.id;

    // Refresh user credits
    await fetchCurrentUser();

    displayAnalysisResults(data);
    trackEvent("analysis_done");
    showToast("¡Análisis completado con éxito!", "success");
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    loading.style.display = "none";
  }
}

function resetToUpload() {
  document.getElementById("results-panel").style.display = "none";
  document.querySelector(".hero-panel").style.display = "block";
  document.getElementById("file-input").value = "";
}

// ==========================================
// RESULTS DISPLAY
// ==========================================
function displayAnalysisResults(data) {
  document.querySelector(".hero-panel").style.display = "none";
  const resultsPanel = document.getElementById("results-panel");
  resultsPanel.style.display = "block";
  loadAIStatus();   // punto verde/rojo junto al título del chat

  // Header
  document.getElementById("res-project-name").textContent = data.project_name || data.filename;
  document.getElementById("res-filename").textContent = data.filename;
  document.getElementById("res-badge-framework").textContent = data.tech_stack?.framework || "Móvil";
  document.getElementById("res-lang").textContent = data.tech_stack?.language || "Multi";
  document.getElementById("res-timestamp").textContent = `Justo ahora · ${regionLabel(data.region || state.region)}`;

  // Hardware Reqs
  const reqs = data.requirements || {};
  document.getElementById("spec-ram").textContent = `Mín ${reqs.min_ram_gb || 3.0} GB / Rec ${reqs.rec_ram_gb || 6.0} GB`;
  document.getElementById("spec-storage").textContent = `${reqs.min_storage_gb || 1.0} GB requeridos`;
  document.getElementById("spec-cpu").textContent = `Mín ${reqs.min_cpu_cores || 4} núcleos`;
  document.getElementById("spec-gpu").textContent = `${reqs.graphics_api || 'OpenGL ES 3.0'} (${(reqs.gpu_tier || 'entry').toUpperCase()})`;
  document.getElementById("spec-os").textContent = `Android ${reqs.min_android_version || 8.0}+ / iOS ${reqs.min_ios_version || 13.0}+`;

  // Heavy features tags
  const tagsContainer = document.getElementById("res-heavy-features");
  tagsContainer.innerHTML = "";
  const features = [...new Set(data.tech_stack?.heavy_features || [])];
  if (features.length === 0) {
    tagsContainer.innerHTML = `<span class="tag-badge">Sin librerías pesadas detectadas</span>`;
  } else {
    features.forEach(feat => {
      const tag = document.createElement("span");
      tag.className = "tag-badge";
      tag.textContent = feat;
      tagsContainer.appendChild(tag);
    });
  }

  // KPIs
  const stats = data.stats || { total: 0, compatible: 0, limited: 0, incompatible: 0 };
  document.getElementById("count-compat").textContent = stats.compatible.toLocaleString();
  document.getElementById("count-limited").textContent = stats.limited.toLocaleString();
  document.getElementById("count-incompat").textContent = stats.incompatible.toLocaleString();
  document.getElementById("total-devices-tested").textContent = stats.total.toLocaleString();

  document.getElementById("pct-compat").textContent = `${stats.compatible_pct || 0}%`;
  document.getElementById("pct-limited").textContent = `${stats.limited_pct || 0}%`;
  document.getElementById("pct-incompat").textContent = `${stats.incompatible_pct || 0}%`;

  // Progress Bar
  document.getElementById("bar-compat").style.width = `${stats.compatible_pct || 0}%`;
  document.getElementById("bar-limited").style.width = `${stats.limited_pct || 0}%`;
  document.getElementById("bar-incompat").style.width = `${stats.incompatible_pct || 0}%`;

  // Filter tab counts
  document.getElementById("tab-count-all").textContent = stats.total.toLocaleString();
  document.getElementById("tab-count-compat").textContent = stats.compatible.toLocaleString();
  document.getElementById("tab-count-limited").textContent = stats.limited.toLocaleString();
  document.getElementById("tab-count-incompat").textContent = stats.incompatible.toLocaleString();

  // AI Summary
  document.getElementById("res-ai-summary").textContent = data.summary || "Compatibilidad calculada con éxito.";

  // Bottlenecks
  const bottlenecksList = document.getElementById("bottlenecks-list");
  bottlenecksList.innerHTML = "";
  (data.bottlenecks || []).forEach(bn => {
    const pill = document.createElement("div");
    pill.className = "bottleneck-pill";
    pill.textContent = `⚠️ ${bn}`;
    bottlenecksList.appendChild(pill);
  });

  // Recommendations
  const recsContainer = document.getElementById("recs-container");
  recsContainer.innerHTML = "";
  (data.recommendations || []).forEach(rec => {
    const card = document.createElement("div");
    card.className = "rec-card";
    card.innerHTML = `
      <div class="rec-category">${rec.category}</div>
      <div class="rec-title">${rec.title}</div>
      <div class="rec-detail">${rec.detail}</div>
    `;
    recsContainer.appendChild(card);
  });

  // Load device compatibility table for this analysis
  state.deviceFilter.skip = 0;
  loadAnalysisDevices();

  // Reset chat thread
  resetChatThread(data.project_name);
}

// ==========================================
// DEVICE COMPATIBILITY MATRIX TABLE
// ==========================================
async function loadAnalysisDevices() {
  if (!state.currentAnalysisId) return;

  const f = state.deviceFilter;
  let url = `${API_BASE}/analysis/${state.currentAnalysisId}?skip=${f.skip}&limit=${f.limit}`;
  if (f.status) url += `&status=${encodeURIComponent(f.status)}`;
  if (f.brand) url += `&brand=${encodeURIComponent(f.brand)}`;
  if (f.search) url += `&search=${encodeURIComponent(f.search)}`;

  try {
    const res = await fetch(url, {
      headers: { "Authorization": `Bearer ${state.token}` }
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    renderDeviceRows(data.devices || []);
    updateDevicePagination(data.devices_pagination || { total: 0, skip: 0, limit: 50 });
  } catch (err) {
    console.error("Error loading analysis devices:", err);
  }
}

function renderDeviceRows(devices) {
  const tbody = document.getElementById("devices-table-body");
  const empty = document.getElementById("devices-empty-state");
  tbody.innerHTML = "";

  if (devices.length === 0) {
    empty.style.display = "block";
    return;
  }
  empty.style.display = "none";

  devices.forEach(item => {
    const d = item.device;
    const tr = document.createElement("tr");

    const statusBadge = `<span class="status-pill ${item.status}">${
      item.status === 'compatible' ? '🟢 Compatible' : (item.status === 'limited' ? '🟡 Limitado' : '🔴 Incompatible')
    }</span>`;

    tr.innerHTML = `
      <td>
        <div class="phone-name">${d.display_name || d.phone_model}</div>
        <div class="phone-brand-sub">${d.phone_brand}</div>
      </td>
      <td><strong>${d.ram_gb ? d.ram_gb + ' GB' : '-'}</strong></td>
      <td>${d.storage_gb ? d.storage_gb + ' GB' : '-'}</td>
      <td>${d.os_type || '-'} ${d.os_version || ''}</td>
      <td title="${d.cpu || ''}">${d.chipset || d.cpu ? (d.chipset || d.cpu).substring(0, 24) + '...' : '-'}</td>
      <td>${statusBadge}</td>
      <td><div class="reason-text">${item.reason}</div></td>
      <td>
        <button class="btn btn-secondary btn-sm" onclick='askAboutDevice(${JSON.stringify(d.display_name || d.phone_model)})'>Consultar</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function updateDevicePagination(pag) {
  state.deviceFilter.total = pag.total;
  const start = pag.total === 0 ? 0 : pag.skip + 1;
  const end = Math.min(pag.skip + pag.limit, pag.total);
  document.getElementById("pagination-info").textContent = `Mostrando ${start} - ${end} de ${pag.total.toLocaleString()} dispositivos`;

  document.getElementById("btn-prev-page").disabled = pag.skip === 0;
  document.getElementById("btn-next-page").disabled = end >= pag.total;
}

function prevDevicePage() {
  if (state.deviceFilter.skip >= state.deviceFilter.limit) {
    state.deviceFilter.skip -= state.deviceFilter.limit;
    loadAnalysisDevices();
  }
}

function nextDevicePage() {
  if (state.deviceFilter.skip + state.deviceFilter.limit < state.deviceFilter.total) {
    state.deviceFilter.skip += state.deviceFilter.limit;
    loadAnalysisDevices();
  }
}

function filterDevicesByStatus(statusVal) {
  state.deviceFilter.status = statusVal;
  state.deviceFilter.skip = 0;

  document.querySelectorAll(".status-tab").forEach(tab => tab.classList.remove("active"));
  event.target.classList.add("active");

  loadAnalysisDevices();
}

function applyDeviceFilters() {
  state.deviceFilter.brand = document.getElementById("device-brand-filter").value;
  state.deviceFilter.skip = 0;
  loadAnalysisDevices();
}

let searchTimeout = null;
function debounceDeviceSearch() {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    state.deviceFilter.search = document.getElementById("device-search-input").value.trim();
    state.deviceFilter.skip = 0;
    loadAnalysisDevices();
  }, 300);
}

// ==========================================
// AI CHAT & Q&A
// ==========================================
// ==========================================
// CHAT: SEGURIDAD Y PRESENTACIÓN
// ==========================================
// Escapa SIEMPRE el texto antes de formatearlo o inyectarlo en el DOM.
function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Etiqueta legible del motor que respondió
const AI_SOURCE_LABELS = {
  regla: "Regla del catálogo",
  heuristica: "Regla del catálogo",
  local: "Sin IA (modo respaldo)",
  sin_ia: "Sin IA (modo respaldo)"
};

function sourceLabel(source) {
  if (!source) return "";
  return AI_SOURCE_LABELS[source] || source;   // "IA deepseek-chat" se muestra tal cual
}

function resetChatThread(projectName) {
  const thread = document.getElementById("chat-thread");
  thread.innerHTML = `
    <div class="chat-msg chat-assistant">
      <div class="msg-author">Asistente AdaptMobile:</div>
      <div class="msg-body">¿Tienes dudas sobre cómo rendirá '${escapeHtml(projectName || "")}' en un teléfono particular? Pregúntame y responderé con las especificaciones verificadas del catálogo.</div>
    </div>
  `;
}

function askAboutDevice(deviceName) {
  const input = document.getElementById("chat-question-input");
  input.value = `¿Cómo correrá el proyecto en el ${deviceName}?`;
  input.focus();
  document.querySelector(".qa-assistant-card").scrollIntoView({ behavior: "smooth" });
}

async function handleSendQuestion(e) {
  e.preventDefault();
  const input = document.getElementById("chat-question-input");
  const question = input.value.trim();
  if (!question || !state.currentAnalysisId) return;

  if (!state.token) {
    openAuthModal("login");
    return;
  }

  appendChatMessage("Tú", question, "chat-user");
  input.value = "";

  const btn = document.getElementById("btn-send-question");
  btn.disabled = true;
  input.disabled = true;
  showTypingIndicator();

  try {
    const res = await fetch(`${API_BASE}/analysis/${state.currentAnalysisId}/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${state.token}`
      },
      body: JSON.stringify({
        analysis_id: state.currentAnalysisId,
        question: question
      })
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (res.status === 402) {
        openPlansModal();
        showCreditsAlert(true);
        throw new Error(errorMessage(data, "Has agotado tus créditos de este mes."));
      }
      if (res.status === 401) {
        handleLogout();
        throw new Error("Tu sesión expiró. Vuelve a iniciar sesión para seguir preguntando.");
      }
      if (res.status === 502 || res.status === 503 || res.status === 504) {
        throw new Error("El servicio de IA no respondió a tiempo. Inténtalo de nuevo en unos segundos.");
      }
      throw new Error(errorMessage(data, "No se pudo procesar la consulta."));
    }

    appendChatMessage("Asistente AdaptMobile", data.answer, "chat-assistant", {
      source: data.source,
      fallback: data.fallback,
      credits: data.credits_remaining
    });
    await fetchCurrentUser(); // Actualiza el contador de créditos de la cabecera
  } catch (err) {
    appendChatMessage("Error", (err && err.message) || "Error al procesar la consulta", "chat-assistant error");
  } finally {
    hideTypingIndicator();
    btn.disabled = false;
    input.disabled = false;
    input.focus();
  }
}

function showTypingIndicator() {
  hideTypingIndicator();
  const thread = document.getElementById("chat-thread");
  if (!thread) return;
  const typing = document.createElement("div");
  typing.id = "chat-typing";
  typing.className = "chat-msg chat-assistant";
  typing.innerHTML = `
    <div class="msg-author">Asistente AdaptMobile:</div>
    <div class="msg-body typing-dots">El asistente está escribiendo<span>.</span><span>.</span><span>.</span></div>
  `;
  thread.appendChild(typing);
  thread.scrollTop = thread.scrollHeight;
}

function hideTypingIndicator() {
  const typing = document.getElementById("chat-typing");
  if (typing) typing.remove();
}

function appendChatMessage(author, text, cssClass, opts) {
  const options = opts || {};
  const thread = document.getElementById("chat-thread");
  const msgDiv = document.createElement("div");
  msgDiv.className = `chat-msg ${cssClass}`;

  // 1) Escapar SIEMPRE (autor, texto y fuente) y solo después aplicar el formato.
  const formattedText = escapeHtml(text)
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br>");

  const label = sourceLabel(options.source);
  const sourceTag = label ? `<span class="msg-source">${escapeHtml(label)}</span>` : "";

  const creditsTag = typeof options.credits === "number"
    ? `<span class="msg-credits">${options.credits} crédito${options.credits === 1 ? "" : "s"} restante${options.credits === 1 ? "" : "s"}</span>`
    : "";

  const adminHint = (options.fallback && state.user && state.user.role === "admin")
    ? `<a href="#" class="msg-fallback-link" onclick="switchTab('admin'); return false;">Configurar la API key</a>`
    : "";

  const fallbackNotice = options.fallback
    ? `<div class="msg-fallback">⚠️ Respuesta en <strong>modo respaldo</strong>: la IA conversacional no está configurada o no está disponible.${adminHint}</div>`
    : "";

  msgDiv.innerHTML = `
    <div class="msg-author">${escapeHtml(author)}:</div>
    <div class="msg-body">${formattedText}</div>
    ${fallbackNotice}
    <div class="msg-meta">${sourceTag}${creditsTag}</div>
  `;
  thread.appendChild(msgDiv);
  thread.scrollTop = thread.scrollHeight;
}

// Punto verde/rojo del estado de la IA en la cabecera del chat
async function loadAIStatus() {
  const dot = document.getElementById("chat-ai-dot");
  const label = document.getElementById("chat-ai-status");
  if (!dot || !label || !state.token) return;

  try {
    const res = await fetch(`${API_BASE}/ai/status`, {
      headers: { "Authorization": `Bearer ${state.token}` }
    });
    if (!res.ok) throw new Error("sin estado");
    const data = await res.json();
    const active = !!data.active;

    dot.className = `chat-ai-dot ${active ? "online" : "offline"}`;
    label.textContent = active ? `IA conectada${data.chat_model ? " · " + data.chat_model : ""}` : "Modo respaldo";
    label.title = active
      ? `IA conversacional activa (${data.key_source || "key configurada"})`
      : `IA no configurada o no disponible${data.key_source ? " (" + data.key_source + ")" : ""}. El chat responderá con el catálogo verificado.`;
  } catch (err) {
    dot.className = "chat-ai-dot offline";
    label.textContent = "Modo respaldo";
    label.title = "No se pudo consultar el estado de la IA.";
  }
}

// ==========================================
// USER HISTORY
// ==========================================
async function loadUserHistory() {
  if (!state.token) {
    openAuthModal("login");
    return;
  }

  const container = document.getElementById("history-container");
  container.innerHTML = `<div class="empty-state"><p>Cargando historial...</p></div>`;

  try {
    const res = await fetch(`${API_BASE}/analysis`, {
      headers: { "Authorization": `Bearer ${state.token}` }
    });
    const items = await res.json();
    if (!res.ok) throw new Error(items.detail);

    if (items.length === 0) {
      container.innerHTML = `<div class="empty-state"><p>Aún no has realizado ningún análisis. ¡Sube tu primer proyecto!</p></div>`;
      return;
    }

    container.innerHTML = "";
    items.forEach(item => {
      const card = document.createElement("div");
      card.className = "history-card";
      const dateStr = new Date(item.created_at).toLocaleDateString("es-ES", {
        day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit"
      });

      card.onclick = () => reopenHistoryAnalysis(item.id);

      const stats = item.stats || { compatible: 0, limited: 0, incompatible: 0 };
      card.innerHTML = `
        <div class="history-card-header">
          <div>
            <div class="history-title">${item.project_name}</div>
            <div class="history-date">${dateStr} • ${regionLabel(item.region)} • <code>${item.filename}</code></div>
          </div>
          <span class="status-pill compatible">${stats.compatible_pct || 0}% Compatible</span>
        </div>
        <div class="multi-progress-bar" style="height: 8px;">
          <div class="bar-part bar-compat" style="width: ${stats.compatible_pct || 0}%;"></div>
          <div class="bar-part bar-limited" style="width: ${stats.limited_pct || 0}%;"></div>
          <div class="bar-part bar-incompat" style="width: ${stats.incompatible_pct || 0}%;"></div>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = `<div class="empty-state"><p>Error cargando historial: ${err.message}</p></div>`;
  }
}

async function reopenHistoryAnalysis(analysisId) {
  try {
    const res = await fetch(`${API_BASE}/analysis/${analysisId}`, {
      headers: { "Authorization": `Bearer ${state.token}` }
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    state.currentAnalysis = data;
    state.currentAnalysisId = data.id;
    switchTab("analyzer");
    displayAnalysisResults(data);
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ==========================================
// DEVICE CATALOG VIEW
// ==========================================
async function loadBrandFilters() {
  try {
    const res = await fetch(`${API_BASE}/devices/brands?region=${state.region}`);
    if (res.ok) {
      const brands = await res.json();
      const devFilter = document.getElementById("device-brand-filter");
      const catFilter = document.getElementById("catalog-brand-filter");
      devFilter.length = 1;   // conserva "Todas las marcas"
      catFilter.length = 1;
      devFilter.value = "";
      catFilter.value = "";

      brands.forEach(b => {
        const opt1 = document.createElement("option");
        opt1.value = b.toLowerCase();
        opt1.textContent = b;
        devFilter.appendChild(opt1);

        const opt2 = document.createElement("option");
        opt2.value = b.toLowerCase();
        opt2.textContent = b;
        catFilter.appendChild(opt2);
      });
    }
  } catch (err) {
    console.error("Error loading brands:", err);
  }
}

async function loadCatalogDevices() {
  const f = state.catalogFilter;
  f.brand = document.getElementById("catalog-brand-filter").value;
  f.os = document.getElementById("catalog-os-filter").value;

  let url = `${API_BASE}/devices?region=${state.region}&skip=${f.skip}&limit=${f.limit}`;
  if (f.brand) url += `&brand=${encodeURIComponent(f.brand)}`;
  if (f.os) url += `&os_type=${encodeURIComponent(f.os)}`;
  if (f.search) url += `&search=${encodeURIComponent(f.search)}`;

  try {
    const res = await fetch(url);
    const devices = await res.json();
    if (!res.ok) throw new Error(devices.detail);

    const tbody = document.getElementById("catalog-table-body");
    tbody.innerHTML = "";

    devices.forEach(d => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="text-transform: capitalize;"><strong>${d.phone_brand}</strong></td>
        <td>${d.phone_model}</td>
        <td>${d.ram_gb ? d.ram_gb + ' GB' : '-'}</td>
        <td>${d.storage_gb ? d.storage_gb + ' GB' : '-'}</td>
        <td>${d.os_type || '-'} ${d.os_version || ''}</td>
        <td>${d.cpu || d.chipset || '-'}</td>
        <td>${d.gpu || '-'}</td>
        <td>${d.display_resolution || '-'}</td>
        <td>${d.release_year || '-'}</td>
      `;
      tbody.appendChild(tr);
    });

    const start = f.skip + 1;
    const end = f.skip + devices.length;
    document.getElementById("catalog-pagination-info").textContent = `Mostrando ${start} - ${end} dispositivos`;
  } catch (err) {
    console.error("Error loading catalog:", err);
  }
}

function debounceCatalogSearch() {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    state.catalogFilter.search = document.getElementById("catalog-search").value.trim();
    state.catalogFilter.skip = 0;
    loadCatalogDevices();
  }, 300);
}

function catalogPrevPage() {
  if (state.catalogFilter.skip >= state.catalogFilter.limit) {
    state.catalogFilter.skip -= state.catalogFilter.limit;
    loadCatalogDevices();
  }
}

function catalogNextPage() {
  state.catalogFilter.skip += state.catalogFilter.limit;
  loadCatalogDevices();
}

// ==========================================
// ADMIN DASHBOARD
// ==========================================
async function loadAdminStats() {
  if (!state.token || !state.user || state.user.role !== "admin") return;

  loadAdminAiKey(); // estado de la API key de DeepSeek (maneja sus propios errores)

  try {
    const auth = { headers: { "Authorization": `Bearer ${state.token}` } };
    const [statsRes, usersRes, usageRes, funnelRes] = await Promise.all([
      fetch(`${API_BASE}/admin/stats`, auth),
      fetch(`${API_BASE}/admin/users`, auth),
      fetch(`${API_BASE}/admin/usage`, auth),
      fetch(`${API_BASE}/admin/funnel`, auth)
    ]);

    if (statsRes.ok) {
      const stats = await statsRes.json();
      document.getElementById("admin-total-users").textContent = stats.total_users;
      document.getElementById("admin-total-analyses").textContent = stats.total_analyses;
      document.getElementById("admin-total-devices").textContent = stats.total_devices.toLocaleString();
      document.getElementById("admin-total-questions").textContent = stats.total_questions;
    }

    if (usersRes.ok) {
      const users = await usersRes.json();
      const tbody = document.getElementById("admin-users-table-body");
      tbody.innerHTML = "";

      users.forEach(u => {
        const tr = document.createElement("tr");
        const dateStr = new Date(u.created_at).toLocaleDateString("es-ES");

        tr.innerHTML = `
          <td>${u.id}</td>
          <td><strong>${u.email}</strong></td>
          <td>${u.full_name || '-'}</td>
          <td><span class="status-pill ${u.role === 'admin' ? 'compatible' : 'limited'}">${u.role.toUpperCase()}</span></td>
          <td><span class="status-pill compatible">${u.plan.toUpperCase()}</span></td>
          <td>${u.credits_used} / ${u.credits_limit}</td>
          <td>${dateStr}</td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="adminResetCredits(${u.id})">Reset Créditos</button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    // Uso total de créditos
    if (usageRes && usageRes.ok) {
      const usage = await usageRes.json();
      document.getElementById("admin-total-credits").textContent = usage.total_credits_spent.toLocaleString();
      document.getElementById("admin-total-usage-events").textContent = usage.total_events.toLocaleString();
      const byAction = Object.entries(usage.by_action || {})
        .map(([k, v]) => `${k}: ${v}`).join(" · ");
      document.getElementById("admin-usage-detail").textContent = byAction || "Sin consumo registrado todavía";
    }

    // Embudo de conversión
    if (funnelRes && funnelRes.ok) {
      const funnel = await funnelRes.json();
      const tbody = document.getElementById("admin-funnel-body");
      tbody.innerHTML = "";
      funnel.steps.forEach(step => {
        const tr = document.createElement("tr");
        const prev = step.from_previous_pct;
        const total = step.from_register_pct;
        const bar = Math.min(100, total || 0);
        tr.innerHTML = `
          <td><strong>${FUNNEL_LABELS[step.event] || step.event}</strong></td>
          <td>${step.count.toLocaleString()}</td>
          <td>${prev === null || prev === undefined ? '—' : prev + '%'}</td>
          <td>
            <div class="funnel-bar-wrap">
              <div class="funnel-bar" style="width:${bar}%"></div>
              <span>${total === null || total === undefined ? '—' : total + '%'}</span>
            </div>
          </td>`;
        tbody.appendChild(tr);
      });
    }
  } catch (err) {
    console.error("Admin stats failed:", err);
  }
}

async function adminResetCredits(userId) {
  try {
    const res = await fetch(`${API_BASE}/admin/users/${userId}/reset-credits`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${state.token}` }
    });
    if (res.ok) {
      showToast("Créditos reseteados para el usuario", "success");
      loadAdminStats();
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ==========================================
// ADMIN: API KEY DE DEEPSEEK (rotación en caliente)
// ==========================================
async function loadAdminAiKey() {
  if (!state.token || !state.user || state.user.role !== "admin") return;

  const modeEl = document.getElementById("ai-key-mode");
  const hintEl = document.getElementById("ai-key-hint");
  if (!modeEl) return;

  try {
    const res = await fetch(`${API_BASE}/admin/ai-key`, {
      headers: { "Authorization": `Bearer ${state.token}` }
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "No se pudo consultar el estado de la API key");
    renderAiKeyStatus(data);
  } catch (err) {
    modeEl.textContent = "No disponible";
    modeEl.className = "status-pill incompatible";
    if (hintEl) {
      hintEl.textContent = err.message;
      hintEl.classList.add("error");
    }
  }
}

function renderAiKeyStatus(data) {
  const modeEl = document.getElementById("ai-key-mode");
  const hintEl = document.getElementById("ai-key-hint");
  const activo = data.mode === "deepseek";

  modeEl.textContent = activo ? `DeepSeek activo · ${data.model || ""}`.trim() : "Heurístico (sin API key)";
  modeEl.className = `status-pill ${activo ? "compatible" : "limited"}`;

  document.getElementById("ai-key-source").textContent = data.key_source || "sin configurar";
  document.getElementById("ai-key-masked").textContent = data.key_masked || "—";
  document.getElementById("ai-key-model").textContent = data.model || "—";

  if (data.last_error) {
    hintEl.textContent = `Último error al llamar a DeepSeek: ${data.last_error}`;
    hintEl.classList.add("error");
  } else {
    hintEl.classList.remove("error");
    hintEl.innerHTML = 'Precedencia: key rotada desde aquí (memoria) → <code>secrets/deepseek_api_key</code> → variable de entorno <code>DEEPSEEK_API_KEY</code>. Si no hay key, el análisis sigue funcionando con el motor heurístico.';
  }
}

async function handleSaveAiKey(e) {
  e.preventDefault();
  const input = document.getElementById("ai-key-input");
  const btn = document.getElementById("btn-save-ai-key");
  const apiKey = input.value.trim();

  if (!apiKey) {
    showToast("Pega una API key antes de guardar", "error");
    return;
  }

  btn.disabled = true;
  btn.textContent = "Guardando...";
  try {
    const res = await fetch(`${API_BASE}/admin/ai-key`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${state.token}`
      },
      body: JSON.stringify({ api_key: apiKey })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "No se pudo guardar la API key");

    input.value = "";
    renderAiKeyStatus(data);
    showToast("API key de DeepSeek actualizada y activa", "success");
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Guardar key";
  }
}

async function handleClearAiKey() {
  const btn = document.getElementById("btn-clear-ai-key");
  btn.disabled = true;
  btn.textContent = "Revirtiendo...";
  try {
    const res = await fetch(`${API_BASE}/admin/ai-key`, {
      method: "DELETE",
      headers: { "Authorization": `Bearer ${state.token}` }
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "No se pudo revertir la API key");

    renderAiKeyStatus(data);
    showToast("Se volvió a la key del archivo / .env", "success");
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Volver a la key del .env / archivo";
  }
}

// ==========================================
// SUBSCRIPTIONS & UPGRADE MODAL
// ==========================================
function openPlansModal() {
  document.getElementById("modal-plans").style.display = "flex";
  trackEvent("pricing_viewed");
}

function closePlansModal() {
  document.getElementById("modal-plans").style.display = "none";
}

async function simulateUpgrade(planName) {
  if (!state.token) {
    closePlansModal();
    openAuthModal("login");
    return;
  }

  try {
    trackEvent("upgrade_clicked");
    const res = await fetch(`${API_BASE}/subscriptions/upgrade`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${state.token}`
      },
      body: JSON.stringify({ plan_name: planName })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    state.user = data;
    updateAuthUI();
    closePlansModal();
    showToast(`¡Plan actualizado a ${planName.toUpperCase()} exitosamente! Créditos recargados.`, "success");
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ==========================================
// MODALS & HELPERS
// ==========================================
function openAuthModal(tab) {
  document.getElementById("modal-auth").style.display = "flex";
  switchAuthTab(tab);
}

function closeAuthModal() {
  document.getElementById("modal-auth").style.display = "none";
}

function switchAuthTab(tab) {
  const formLogin = document.getElementById("form-login");
  const formReg = document.getElementById("form-register");
  const tabLogin = document.getElementById("tab-login");
  const tabReg = document.getElementById("tab-register");

  if (tab === "login") {
    formLogin.style.display = "block";
    formReg.style.display = "none";
    tabLogin.classList.add("active");
    tabReg.classList.remove("active");
  } else {
    formLogin.style.display = "none";
    formReg.style.display = "block";
    tabLogin.classList.remove("active");
    tabReg.classList.add("active");
  }
}

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 4000);
}

function setupEventListeners() {
  // Close dropdown on outside click
  window.addEventListener("click", (e) => {
    if (!e.target.closest(".user-menu-trigger") && !e.target.closest(".user-dropdown")) {
      document.getElementById("user-dropdown").classList.remove("open");
    }
  });
}
