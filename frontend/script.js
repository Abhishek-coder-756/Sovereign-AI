(() => {
  "use strict";

  // ================= STATE =================

  let token = localStorage.getItem("sovereign_token") || null;
  let currentUser = null; // { username, role, company }
  let pendingImage = null; // File staged for the next chat message
  let currentConversationId = null; // Active persistent conversation ID
  let activeUploadedFiles = []; // Files attached to active conversation
  let activeUploadedImages = []; // Images attached to active conversation
  let currentKnowledgeMode = "private"; // "private" or "global"
  let activeGlobalSources = []; // Global sources for active conversation

  // ================= DOM =================

  const loginScreen = document.getElementById("loginScreen");
  const appShell = document.getElementById("app");
  const loginForm = document.getElementById("loginForm");
  const loginError = document.getElementById("loginError");
  const loginSubmit = document.getElementById("loginSubmit");

  const sidebar = document.getElementById("sidebar");
  const sidebarToggle = document.getElementById("sidebarToggle");
  const sidebarCollapseBtn = document.getElementById("sidebarCollapseBtn");
  const userProfileBtn = document.getElementById("userProfileBtn");
  const conversationList = document.getElementById("conversationList");
  const navItems = document.querySelectorAll(".nav-item");
  const newChatBtn = document.getElementById("newChatBtn");
  const logoutBtn = document.getElementById("logoutBtn");

  // Knowledge Mode DOM
  const modePrivateBtn = document.getElementById("modePrivateBtn");
  const modeGlobalBtn = document.getElementById("modeGlobalBtn");
  const modeDescText = document.getElementById("modeDescText");
  const modeIndicatorPill = document.getElementById("modeIndicatorPill");
  const modePillText = document.getElementById("modePillText");
  const globalSourceBar = document.getElementById("globalSourceBar");
  const globalUrlInput = document.getElementById("globalUrlInput");
  const globalAddBtn = document.getElementById("globalAddBtn");
  const globalSourcesList = document.getElementById("globalSourcesList");

  const chatHeaderTitle = document.getElementById("chatHeaderTitle");
  const chatScroll = document.getElementById("chatScroll");
  const chatEmpty = document.getElementById("chatEmpty");
  const messagesEl = document.getElementById("messages");
  const chatInput = document.getElementById("chatInput");
  const sendBtn = document.getElementById("sendBtn");
  const openUploadModalBtn = document.getElementById("openUploadModalBtn");
  const attachPdfBtn = document.getElementById("attachPdfBtn");
  const attachImageBtn = document.getElementById("attachImageBtn");
  const attachWrapper = document.getElementById("attachWrapper");
  const attachMenuBtn = document.getElementById("attachMenuBtn");
  const attachDropdown = document.getElementById("attachDropdown");
  const menuUploadFile = document.getElementById("menuUploadFile");
  const menuUploadImage = document.getElementById("menuUploadImage");
  const docFileInputUniversal = document.getElementById("docFileInputUniversal");
  const imageFileInputUniversal = document.getElementById("imageFileInputUniversal");
  const pdfFileInput = document.getElementById("pdfFileInput");
  const imageFileInput = document.getElementById("imageFileInput");
  const attachmentStrip = document.getElementById("attachmentStrip");
  const activeAttachmentsBar = document.getElementById("activeAttachmentsBar");
  const activeAttachmentsList = document.getElementById("activeAttachmentsList");
  const llmStatusPill = document.getElementById("llmStatusPill");

  // Profile modal DOM
  const profileModal = document.getElementById("profileModal");
  const profileModalCard = document.getElementById("profileModalCard");
  const closeProfileModalBtn = document.getElementById("closeProfileModalBtn");
  const profileLogoutBtn = document.getElementById("profileLogoutBtn");
  const profileUsername = document.getElementById("profileUsername");
  const profileRole = document.getElementById("profileRole");
  const profileCompany = document.getElementById("profileCompany");

  // Upload modal & empty card DOM
  const uploadModal = document.getElementById("uploadModal");
  const uploadModalCard = document.getElementById("uploadModalCard");
  const closeUploadModalBtn = document.getElementById("closeUploadModalBtn");
  const modalDropzone = document.getElementById("modalDropzone");
  const modalFileInput = document.getElementById("modalFileInput");
  const browseModalFilesBtn = document.getElementById("browseModalFilesBtn");
  const modalUploadStatus = document.getElementById("modalUploadStatus");
  const modalUploadedSection = document.getElementById("modalUploadedSection");
  const modalUploadedGrid = document.getElementById("modalUploadedGrid");
  const emptyUploadCard = document.getElementById("emptyUploadCard");
  const emptyCardDropzone = document.getElementById("emptyCardDropzone");
  const emptyBrowseBtn = document.getElementById("emptyBrowseBtn");
  const emptyUploadStatus = document.getElementById("emptyUploadStatus");
  const emptyUploadedWrap = document.getElementById("emptyUploadedWrap");
  const emptyUploadedList = document.getElementById("emptyUploadedList");
  const techByteLogo = document.getElementById("techByteLogo");

  // Landing & Registration DOM
  const landingCard = document.getElementById("landingCard");
  const btnLandingSignIn = document.getElementById("btnLandingSignIn");
  const btnLandingRegister = document.getElementById("btnLandingRegister");
  const signInCard = document.getElementById("signInCard");
  const btnBackFromSignIn = document.getElementById("btnBackFromSignIn");
  const linkGoToRegister = document.getElementById("linkGoToRegister");
  const registerCard = document.getElementById("registerCard");
  const registerForm = document.getElementById("registerForm");
  const btnBackFromRegister = document.getElementById("btnBackFromRegister");
  const linkGoToSignIn = document.getElementById("linkGoToSignIn");
  const regName = document.getElementById("regName");
  const regUsername = document.getElementById("regUsername");
  const regMobile = document.getElementById("regMobile");
  const regRole = document.getElementById("regRole");
  const regPassword = document.getElementById("regPassword");
  const regConfirmPassword = document.getElementById("regConfirmPassword");
  const regCompany = document.getElementById("regCompany");
  const regSubmit = document.getElementById("regSubmit");
  const regError = document.getElementById("regError");
  const regSuccess = document.getElementById("regSuccess");
  const prefixHintDesc = document.getElementById("prefixHintDesc");

  // Admin Panel DOM
  const adminNavGroup = document.getElementById("adminNavGroup");
  const navAdminBtn = document.getElementById("navAdminBtn");
  const adminRefreshBtn = document.getElementById("adminRefreshBtn");
  const statTotalUsers = document.getElementById("statTotalUsers");
  const statPending = document.getElementById("statPending");
  const statApproved = document.getElementById("statApproved");
  const statActive = document.getElementById("statActive");
  const statDisabled = document.getElementById("statDisabled");
  const statEmployees = document.getElementById("statEmployees");
  const statOperators = document.getElementById("statOperators");
  const statAdmins = document.getElementById("statAdmins");
  const tabPendingBadge = document.getElementById("tabPendingBadge");
  const adminTabPendingBtn = document.getElementById("adminTabPendingBtn");
  const adminTabUsersBtn = document.getElementById("adminTabUsersBtn");
  const adminTabAuditBtn = document.getElementById("adminTabAuditBtn");
  const adminTabPending = document.getElementById("adminTabPending");
  const adminTabUsers = document.getElementById("adminTabUsers");
  const adminTabAudit = document.getElementById("adminTabAudit");
  const adminPendingTableBody = document.getElementById("adminPendingTableBody");
  const adminPendingEmpty = document.getElementById("adminPendingEmpty");
  const adminUsersTableBody = document.getElementById("adminUsersTableBody");
  const adminUsersEmpty = document.getElementById("adminUsersEmpty");
  const adminAuditTableBody = document.getElementById("adminAuditTableBody");
  const adminAuditEmpty = document.getElementById("adminAuditEmpty");



  // ================= HELPERS =================

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function formatSize(bytes) {
    if (bytes == null) return "\u2014";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(2) + " MB";
  }

  function formatTimestamp(ts) {
    if (!ts) return "\u2014";
    try {
      const d = new Date(ts);
      return d.toLocaleString();
    } catch (e) {
      return ts;
    }
  }

  async function api(path, options = {}) {
    const headers = options.headers || {};
    if (token) headers["Authorization"] = "Bearer " + token;

    const response = await fetch(path, { ...options, headers });

    if (response.status === 401) {
      handleSessionExpired();
      throw new Error("Your session has expired. Please log in again.");
    }

    let data = null;
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      data = await response.json();
    }

    if (!response.ok) {
      const detail = (data && data.detail) ? data.detail : `Request failed (${response.status}).`;
      const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      err.status = response.status;
      throw err;
    }

    return data;
  }

  function handleSessionExpired() {
    token = null;
    currentUser = null;
    localStorage.removeItem("sovereign_token");
    appShell.hidden = true;
    loginScreen.hidden = false;
    showSignIn();
    showLoginError("Your session has expired. Please log in again.");
  }

  function showLoginError(msg) {
    if (loginError) {
      loginError.textContent = msg;
      loginError.hidden = false;
    }
  }

  function showRegError(msg) {
    if (regError) {
      regError.textContent = msg;
      regError.hidden = false;
    }
  }

  // ================= LANDING & AUTH NAVIGATION =================

  function showLanding() {
    if (landingCard) {
      landingCard.hidden = false;
      landingCard.style.display = "";
    }
    if (signInCard) {
      signInCard.hidden = true;
      signInCard.style.display = "none";
    }
    if (registerCard) {
      registerCard.hidden = true;
      registerCard.style.display = "none";
    }
    if (loginError) loginError.hidden = true;
    if (regError) regError.hidden = true;
    if (regSuccess) regSuccess.hidden = true;
  }

  function showSignIn() {
    if (landingCard) {
      landingCard.hidden = true;
      landingCard.style.display = "none";
    }
    if (signInCard) {
      signInCard.hidden = false;
      signInCard.style.display = "";
    }
    if (registerCard) {
      registerCard.hidden = true;
      registerCard.style.display = "none";
    }
    if (loginError) loginError.hidden = true;
    const userField = document.getElementById("loginUsername");
    if (userField) userField.focus();
  }

  async function showRegister() {
    if (landingCard) {
      landingCard.hidden = true;
      landingCard.style.display = "none";
    }
    if (signInCard) {
      signInCard.hidden = true;
      signInCard.style.display = "none";
    }
    if (registerCard) {
      registerCard.hidden = false;
      registerCard.style.display = "";
    }
    if (regError) regError.hidden = true;
    if (regSuccess) regSuccess.hidden = true;
    await loadCompaniesForRegister();
    const nameField = document.getElementById("regName");
    if (nameField) nameField.focus();
  }

  window.showLanding = showLanding;
  window.showSignIn = showSignIn;
  window.showRegister = showRegister;

  async function loadCompaniesForRegister() {
    if (!regCompany) return;
    try {
      const res = await fetch("/api/companies");
      if (res.ok) {
        const comps = await res.json();
        if (comps && comps.length > 0) {
          regCompany.innerHTML = "";
          comps.forEach((c) => {
            const opt = document.createElement("option");
            opt.value = c.name;
            opt.textContent = c.name;
            if (c.name === "MRPL") opt.selected = true;
            regCompany.appendChild(opt);
          });
        }
      }
    } catch (e) {
      // Keep MRPL as default
    }
  }

  if (btnLandingSignIn) btnLandingSignIn.addEventListener("click", showSignIn);
  if (btnLandingRegister) btnLandingRegister.addEventListener("click", showRegister);
  if (btnBackFromSignIn) btnBackFromSignIn.addEventListener("click", showLanding);
  if (btnBackFromRegister) btnBackFromRegister.addEventListener("click", showLanding);
  if (linkGoToRegister) linkGoToRegister.addEventListener("click", (e) => { e.preventDefault(); showRegister(); });
  if (linkGoToSignIn) linkGoToSignIn.addEventListener("click", (e) => { e.preventDefault(); showSignIn(); });

  // Role prefix hint update
  if (regRole && prefixHintDesc) {
    regRole.addEventListener("change", () => {
      const role = regRole.value;
      if (role === "admin") {
        prefixHintDesc.innerHTML = "Admin passwords must start with <code>admin</code> (e.g. <code>adminSecret123</code>, min. 8 chars).";
        if (regPassword) regPassword.placeholder = "e.g. adminMasterPass26!";
      } else if (role === "operator") {
        prefixHintDesc.innerHTML = "Operator passwords must start with <code>operator</code> (e.g. <code>operatorShift26</code>, min. 8 chars).";
        if (regPassword) regPassword.placeholder = "e.g. operatorPass456!";
      } else if (role === "employee") {
        prefixHintDesc.innerHTML = "Employee passwords must start with <code>emp</code> (e.g. <code>empWorkerPass26</code>, min. 8 chars).";
        if (regPassword) regPassword.placeholder = "e.g. empWorker789!";
      } else {
        prefixHintDesc.innerHTML = "Please select a role to view password prefix requirements.";
        if (regPassword) regPassword.placeholder = "Enter role-prefixed password";
      }
    });
  }

  // ================= REGISTRATION SUBMIT =================

  if (registerForm) {
    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (regError) regError.hidden = true;
      if (regSuccess) regSuccess.hidden = true;
      if (regSubmit) {
        regSubmit.disabled = true;
        regSubmit.textContent = "Submitting registration\u2026";
      }

      const name = regName ? regName.value.trim() : "";
      const username = regUsername ? regUsername.value.trim().toLowerCase() : "";
      const mobile = regMobile ? regMobile.value.trim() : "";
      const role = regRole ? regRole.value : "";
      const password = regPassword ? regPassword.value : "";
      const confirmPassword = regConfirmPassword ? regConfirmPassword.value : "";
      const company = regCompany ? regCompany.value : "MRPL";

      // Frontend validation
      if (!name || name.length < 2) {
        showRegError("Full name must be at least 2 characters.");
        if (regSubmit) { regSubmit.disabled = false; regSubmit.textContent = "Submit Registration"; }
        return;
      }
      if (!username || username.length < 3) {
        showRegError("Username must be at least 3 characters.");
        if (regSubmit) { regSubmit.disabled = false; regSubmit.textContent = "Submit Registration"; }
        return;
      }
      if (!role) {
        showRegError("Please select an account role.");
        if (regSubmit) { regSubmit.disabled = false; regSubmit.textContent = "Submit Registration"; }
        return;
      }
      if (password !== confirmPassword) {
        showRegError("Passwords do not match.");
        if (regSubmit) { regSubmit.disabled = false; regSubmit.textContent = "Submit Registration"; }
        return;
      }
      const requiredPrefix = role === "admin" ? "admin" : (role === "operator" ? "operator" : (role === "employee" ? "emp" : ""));
      if (requiredPrefix && !password.startsWith(requiredPrefix)) {
        showRegError(`${role.charAt(0).toUpperCase() + role.slice(1)} password must start with '${requiredPrefix}'.`);
        if (regSubmit) { regSubmit.disabled = false; regSubmit.textContent = "Submit Registration"; }
        return;
      }
      if (password.length < 8) {
        showRegError("Password must be at least 8 characters long.");
        if (regSubmit) { regSubmit.disabled = false; regSubmit.textContent = "Submit Registration"; }
        return;
      }

      try {
        const response = await fetch("/api/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name,
            username,
            mobile,
            role,
            password,
            confirm_password: confirmPassword,
            company,
          }),
        });

        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || "Registration failed.");
        }

        if (regSuccess) {
          regSuccess.innerHTML = `
            <div>&check; <strong>Registration submitted successfully.</strong></div>
            <div style="font-size:12px; margin: 4px 0 8px; color: var(--text-primary);">
              Your account is pending administrator approval.
            </div>
            <button type="button" class="btn-primary btn-sm" id="btnGoToSignInAfterReg">Go to Sign In</button>
          `;
          regSuccess.hidden = false;
          const proceedBtn = document.getElementById("btnGoToSignInAfterReg");
          if (proceedBtn) proceedBtn.addEventListener("click", showSignIn);
        }

        registerForm.reset();
        if (prefixHintDesc) prefixHintDesc.innerHTML = "Please select a role to view password prefix requirements.";

      } catch (err) {
        showRegError(err.message || "Registration failed. Please try again.");
      } finally {
        if (regSubmit) {
          regSubmit.disabled = false;
          regSubmit.textContent = "Submit Registration";
        }
      }
    });
  }

  // ================= LOGIN SUBMIT =================

  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    loginError.hidden = true;
    loginSubmit.disabled = true;
    loginSubmit.textContent = "Signing in\u2026";

    const username = document.getElementById("loginUsername").value.trim();
    const password = document.getElementById("loginPassword").value;

    try {
      const body = new URLSearchParams();
      body.set("username", username);
      body.set("password", password);

      const response = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body.toString(),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Invalid username or password.");
      }

      token = data.access_token;
      currentUser = {
        username: data.username,
        name: data.name || data.username,
        role: data.role,
        company: data.company,
        status: data.status || "APPROVED",
      };
      localStorage.setItem("sovereign_token", token);

      enterApp();
    } catch (err) {
      showLoginError(err.message || "Invalid username or password.");
    } finally {
      loginSubmit.disabled = false;
      loginSubmit.textContent = "Sign in";
    }
  });

  async function enterApp() {
    if (!currentUser) {
      try {
        currentUser = await api("/api/me");
      } catch (e) {
        return; // handleSessionExpired already ran
      }
    }

    document.getElementById("sidebarUsername").textContent = currentUser.username;
    document.getElementById("sidebarRole").textContent = currentUser.role;
    document.getElementById("sidebarCompany").textContent = currentUser.company;
    document.getElementById("userAvatar").textContent = (currentUser.username || "A").charAt(0).toUpperCase();

    if (profileUsername) profileUsername.textContent = currentUser.username;
    if (profileRole) profileRole.textContent = currentUser.role;
    if (profileCompany) profileCompany.textContent = currentUser.company;
    if (userProfileBtn) userProfileBtn.setAttribute("data-tooltip", `${currentUser.username} (${currentUser.role})`);

    // RBAC: Show Admin Panel only to admin role
    const isAdmin = currentUser.role === "admin";
    if (adminNavGroup) adminNavGroup.hidden = !isAdmin;
    if (navAdminBtn) navAdminBtn.hidden = !isAdmin;

    loginScreen.hidden = true;
    appShell.hidden = false;

    refreshHealth();
    setInterval(refreshHealth, 30000);

    // If admin, preload dashboard stats
    if (isAdmin) {
      loadAdminStats();
    }

    // Load persistent conversation list on login
    await loadConversations();
    try {
      const convs = await api("/api/conversations");
      if (convs && convs.length > 0) {
        await selectConversation(convs[0].conversation_id);
      } else {
        await startNewChat();
      }
    } catch (e) {
      // Non-fatal
    }
  }

  logoutBtn.addEventListener("click", () => {
    token = null;
    currentUser = null;
    currentConversationId = null;
    activeUploadedFiles = [];
    activeUploadedImages = [];
    localStorage.removeItem("sovereign_token");
    loginScreen.hidden = false;
    appShell.hidden = true;
    loginForm.reset();
    showLanding();
  });

  // ================= SIDEBAR NAV & COLLAPSE =================

  sidebarToggle.addEventListener("click", () => sidebar.classList.toggle("open"));

  // Restore sidebar collapsed state from localStorage
  const savedCollapsed = localStorage.getItem("sidebar_collapsed") === "true";
  if (savedCollapsed) {
    sidebar.classList.add("collapsed");
    if (sidebarCollapseBtn) {
      sidebarCollapseBtn.title = "Expand sidebar";
      sidebarCollapseBtn.setAttribute("aria-label", "Expand sidebar");
    }
  }

  if (sidebarCollapseBtn) {
    sidebarCollapseBtn.addEventListener("click", () => {
      const isCollapsed = sidebar.classList.toggle("collapsed");
      localStorage.setItem("sidebar_collapsed", isCollapsed ? "true" : "false");
      sidebarCollapseBtn.title = isCollapsed ? "Expand sidebar" : "Collapse sidebar";
      sidebarCollapseBtn.setAttribute("aria-label", isCollapsed ? "Expand sidebar" : "Collapse sidebar");
    });
  }

  // Allow clicking brand group or logo in collapsed state to expand
  function expandSidebarIfCollapsed() {
    if (sidebar.classList.contains("collapsed")) {
      sidebar.classList.remove("collapsed");
      localStorage.setItem("sidebar_collapsed", "false");
      if (sidebarCollapseBtn) {
        sidebarCollapseBtn.title = "Collapse sidebar";
        sidebarCollapseBtn.setAttribute("aria-label", "Collapse sidebar");
      }
    }
  }

  const sidebarBrandGroup = document.getElementById("sidebarBrandGroup");
  if (sidebarBrandGroup) {
    sidebarBrandGroup.addEventListener("click", expandSidebarIfCollapsed);
  }
  if (techByteLogo) {
    techByteLogo.addEventListener("click", (e) => {
      if (sidebar.classList.contains("collapsed")) {
        e.stopPropagation();
        expandSidebarIfCollapsed();
      }
    });
  }

  // ================= ADMIN PROFILE / TEAM PANEL =================

  function openProfileModal() {
    if (profileUsername) profileUsername.textContent = currentUser?.username || "admin";
    if (profileRole) profileRole.textContent = currentUser?.role || "Admin";
    if (profileCompany) profileCompany.textContent = currentUser?.company || "MRPL";
    if (profileModal) profileModal.hidden = false;
  }

  function closeProfileModal() {
    if (profileModal) profileModal.hidden = true;
  }

  if (userProfileBtn) {
    userProfileBtn.addEventListener("click", openProfileModal);
  }
  if (closeProfileModalBtn) {
    closeProfileModalBtn.addEventListener("click", closeProfileModal);
  }
  if (profileModal) {
    profileModal.addEventListener("click", (e) => {
      if (e.target === profileModal) closeProfileModal();
    });
  }
  if (profileLogoutBtn) {
    profileLogoutBtn.addEventListener("click", () => {
      closeProfileModal();
      logoutBtn.click();
    });
  }

  navItems.forEach((btn) => {
    btn.addEventListener("click", () => {
      navItems.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
      const view = document.getElementById("view-" + btn.dataset.view);
      if (view) view.classList.remove("hidden");
      sidebar.classList.remove("open");

      if (btn.dataset.view === "documents") loadDocuments();
      if (btn.dataset.view === "audit") loadAudit();
      if (btn.dataset.view === "status") loadStatus();
      if (btn.dataset.view === "admin") loadAdminDashboard();
    });
  });

  // ================= KNOWLEDGE MODE SWITCHER =================

  function setKnowledgeMode(mode) {
    currentKnowledgeMode = (mode === "global") ? "global" : "private";

    if (modePrivateBtn && modeGlobalBtn) {
      modePrivateBtn.classList.toggle("active", currentKnowledgeMode === "private");
      modeGlobalBtn.classList.toggle("active", currentKnowledgeMode === "global");
    }

    if (modeDescText) {
      modeDescText.textContent = currentKnowledgeMode === "private"
        ? "Company Knowledge \u00b7 On-premise documents only"
        : "Public Knowledge \u00b7 Explicitly provided public web sources";
    }

    if (modeIndicatorPill && modePillText) {
      modeIndicatorPill.className = "status-pill mode-indicator-pill " + currentKnowledgeMode;
      modePillText.textContent = currentKnowledgeMode === "private" ? "🏢 PRIVATE MODE" : "🌐 GLOBAL MODE";
    }

    if (globalSourceBar) {
      globalSourceBar.hidden = (currentKnowledgeMode !== "global");
    }

    if (chatInput) {
      chatInput.placeholder = currentKnowledgeMode === "private"
        ? "Ask anything about documents, spreadsheets, or images..."
        : "Ask anything about the added public web sources...";
    }
  }

  if (modePrivateBtn) {
    modePrivateBtn.addEventListener("click", () => setKnowledgeMode("private"));
  }
  if (modeGlobalBtn) {
    modeGlobalBtn.addEventListener("click", () => setKnowledgeMode("global"));
  }

  // ================= GLOBAL SOURCES MANAGEMENT =================

  function renderGlobalSources() {
    if (!globalSourcesList) return;
    if (!activeGlobalSources || activeGlobalSources.length === 0) {
      globalSourcesList.innerHTML = `<span class="muted" style="font-size:11.5px;">No public web sources added yet. Paste a URL above and click "+ Add Source".</span>`;
      return;
    }

    globalSourcesList.innerHTML = activeGlobalSources.map((s) => {
      const title = s.title || s.url || "Public Source";
      const sId = s.id || s.source_id;
      return `
        <div class="global-source-chip" data-id="${escapeHtml(String(sId))}">
          <span class="global-chip-title" title="${escapeHtml(title)}">${escapeHtml(title)}</span>
          <a class="global-chip-url" href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(s.url)}">${escapeHtml(s.url)}</a>
          <button type="button" class="global-chip-del" title="Remove source" data-id="${escapeHtml(String(sId))}">&times;</button>
        </div>
      `;
    }).join("");

    globalSourcesList.querySelectorAll(".global-chip-del").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const sourceId = btn.dataset.id;
        await removeGlobalSource(sourceId);
      });
    });
  }

  async function addGlobalSource(url) {
    const rawUrl = (url || "").trim();
    if (!rawUrl) return;

    if (!rawUrl.startsWith("http://") && !rawUrl.startsWith("https://")) {
      alert("Please enter a valid HTTP or HTTPS URL (e.g. https://en.wikipedia.org/wiki/Artificial_intelligence).");
      return;
    }

    if (globalAddBtn) {
      globalAddBtn.disabled = true;
      globalAddBtn.textContent = "Fetching...";
    }

    try {
      const res = await api("/api/global/sources", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: currentConversationId || "",
          url: rawUrl,
        }),
      });

      if (res.conversation_id && !currentConversationId) {
        currentConversationId = res.conversation_id;
        await loadConversations();
      }

      if (res.global_sources) {
        activeGlobalSources = res.global_sources;
      } else if (res.source) {
        activeGlobalSources.push(res.source);
      }

      renderGlobalSources();
      if (globalUrlInput) globalUrlInput.value = "";
    } catch (err) {
      alert("Failed to add public source: " + (err.message || "Unknown error"));
    } finally {
      if (globalAddBtn) {
        globalAddBtn.disabled = false;
        globalAddBtn.textContent = "+ Add Source";
      }
    }
  }

  async function removeGlobalSource(sourceId) {
    if (!currentConversationId) return;
    try {
      const res = await api(`/api/global/sources/${sourceId}?conversation_id=${currentConversationId}`, {
        method: "DELETE",
      });
      if (res.global_sources) {
        activeGlobalSources = res.global_sources;
      } else {
        activeGlobalSources = activeGlobalSources.filter((s) => String(s.id) !== String(sourceId));
      }
      renderGlobalSources();
    } catch (err) {
      alert("Failed to remove source: " + err.message);
    }
  }

  if (globalAddBtn) {
    globalAddBtn.addEventListener("click", () => {
      if (globalUrlInput) addGlobalSource(globalUrlInput.value);
    });
  }
  if (globalUrlInput) {
    globalUrlInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        addGlobalSource(globalUrlInput.value);
      }
    });
  }

  newChatBtn.addEventListener("click", () => {
    startNewChat();
  });

  // ================= CONVERSATIONS (ChatGPT-Style) =================

  async function loadConversations() {
    try {
      const list = await api("/api/conversations");
      renderConversationList(list);
    } catch (e) {
      // non-fatal
    }
  }

  function renderConversationList(list) {
    if (!conversationList) return;
    if (!list || list.length === 0) {
      conversationList.innerHTML = `<div class="conv-empty muted">No previous chats</div>`;
      return;
    }
    conversationList.innerHTML = "";
    list.forEach((conv) => {
      const item = document.createElement("div");
      item.className = "conv-item" + (conv.conversation_id === currentConversationId ? " active" : "");
      item.dataset.id = conv.conversation_id;
      item.innerHTML = `
        <span class="conv-item-title" title="${escapeHtml(conv.title)}">${escapeHtml(conv.title)}</span>
        <button class="conv-item-del" title="Delete conversation">&times;</button>
      `;
      item.addEventListener("click", (e) => {
        if (e.target.classList.contains("conv-item-del")) return;
        selectConversation(conv.conversation_id);
      });
      item.querySelector(".conv-item-del").addEventListener("click", async (e) => {
        e.stopPropagation();
        if (confirm(`Delete conversation "${conv.title}"?`)) {
          try {
            await api(`/api/conversations/${conv.conversation_id}`, { method: "DELETE" });
            if (currentConversationId === conv.conversation_id) {
              await startNewChat();
            } else {
              await loadConversations();
            }
          } catch (err) {
            alert("Delete failed: " + err.message);
          }
        }
      });
      conversationList.appendChild(item);
    });
  }

  async function selectConversation(convId) {
    try {
      const conv = await api(`/api/conversations/${convId}`);
      currentConversationId = conv.conversation_id;
      if (chatHeaderTitle) {
        chatHeaderTitle.textContent = conv.title || "SOVEREIGN AI";
      }
      clearPendingImage();
      messagesEl.innerHTML = "";

      activeUploadedFiles = conv.uploaded_files || [];
      activeUploadedImages = conv.uploaded_images || [];
      activeGlobalSources = conv.global_sources || [];
      renderActiveAttachments();
      renderModalUploadedFiles();
      renderGlobalSources();

      if (!conv.messages || conv.messages.length === 0) {
        chatEmpty.style.display = "";
      } else {
        chatEmpty.style.display = "none";
        conv.messages.forEach((msg) => {
          if (msg.role === "user") {
            appendUserMessage(msg.content);
          } else {
            const meta = msg.metadata || {};
            appendAiMessage({
              answer: msg.content,
              sources: meta.sources,
              verification: meta.verification,
              imageObservation: meta.image_observation,
              model: meta.model,
              executionTime: meta.execution_time,
              agentSteps: meta.agent_steps,
              intent: meta.intent,
            });
          }
        });
      }

      // Highlight in sidebar
      document.querySelectorAll(".conv-item").forEach((el) => {
        el.classList.toggle("active", el.dataset.id === convId);
      });

      // Switch view to chat
      navItems.forEach((b) => b.classList.remove("active"));
      const chatTab = document.querySelector('.nav-item[data-view="chat"]');
      if (chatTab) chatTab.classList.add("active");
      document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
      const chatView = document.getElementById("view-chat");
      if (chatView) chatView.classList.remove("hidden");
    } catch (e) {
      console.error("Failed to select conversation:", e);
    }
  }

  async function startNewChat() {
    try {
      const conv = await api("/api/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "New Chat" }),
      });
      currentConversationId = conv.conversation_id;
      if (chatHeaderTitle) {
        chatHeaderTitle.textContent = "SOVEREIGN AI";
      }
      messagesEl.innerHTML = "";
      chatEmpty.style.display = "";
      clearPendingImage();
      activeUploadedFiles = [];
      activeUploadedImages = [];
      activeGlobalSources = [];
      renderActiveAttachments();
      renderModalUploadedFiles();
      renderGlobalSources();
      await loadConversations();

      navItems.forEach((b) => b.classList.remove("active"));
      const chatTab = document.querySelector('.nav-item[data-view="chat"]');
      if (chatTab) chatTab.classList.add("active");
      document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
      const chatView = document.getElementById("view-chat");
      if (chatView) chatView.classList.remove("hidden");
    } catch (e) {
      console.error("Failed to start new chat:", e);
    }
  }

  function renderActiveAttachments() {
    if (!activeAttachmentsBar || !activeAttachmentsList) return;
    const allFiles = [
      ...activeUploadedFiles.map((f) => ({ name: f, isImage: false })),
      ...activeUploadedImages.map((img) => ({ name: img.split("/").pop(), path: img, isImage: true })),
    ];

    if (allFiles.length === 0) {
      activeAttachmentsBar.hidden = true;
      activeAttachmentsList.innerHTML = "";
      return;
    }

    activeAttachmentsBar.hidden = false;
    activeAttachmentsList.innerHTML = "";
    allFiles.forEach((item) => {
      const chip = document.createElement("span");
      chip.className = "active-attachment-chip";
      const icon = item.isImage ? "\uD83D\uDDBC" : "\uD83D\uDCC4";
      chip.innerHTML = `
        <span>${icon}</span>
        <span class="chip-name" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</span>
        <button class="active-attachment-del" title="Detach from chat">&times;</button>
      `;
      chip.querySelector(".active-attachment-del").addEventListener("click", async () => {
        if (!currentConversationId) return;
        try {
          await api(`/api/conversations/${currentConversationId}/attachments/${encodeURIComponent(item.name)}`, {
            method: "DELETE",
          });
          if (item.isImage) {
            activeUploadedImages = activeUploadedImages.filter((img) => img.split("/").pop() !== item.name && img !== item.name);
          } else {
            activeUploadedFiles = activeUploadedFiles.filter((f) => f !== item.name);
          }
          renderActiveAttachments();
          renderModalUploadedFiles();
        } catch (err) {
          alert("Could not detach file: " + err.message);
        }
      });
      activeAttachmentsList.appendChild(chip);
    });
  }

  function createUploadedCardElement(item) {
    const card = document.createElement("div");
    card.className = "uploaded-file-card-sm";
    const icon = item.isImage ? "🖼" : "📄";
    card.innerHTML = `
      <div class="file-left">
        <span class="file-icon">${icon}</span>
        <div class="file-info">
          <div class="file-name" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</div>
          <div class="file-status-line">&check; Uploaded &amp; Active</div>
        </div>
      </div>
      <button type="button" class="file-del-btn" title="Detach attachment">&times;</button>
    `;
    card.querySelector(".file-del-btn").addEventListener("click", async () => {
      if (!currentConversationId) return;
      try {
        await api(`/api/conversations/${currentConversationId}/attachments/${encodeURIComponent(item.name)}`, {
          method: "DELETE",
        });
        if (item.isImage) {
          activeUploadedImages = activeUploadedImages.filter((img) => img.split("/").pop() !== item.name && img !== item.name);
        } else {
          activeUploadedFiles = activeUploadedFiles.filter((f) => f !== item.name);
        }
        renderActiveAttachments();
        renderModalUploadedFiles();
      } catch (err) {
        alert("Could not remove file: " + err.message);
      }
    });
    return card;
  }

  function renderModalUploadedFiles() {
    const allFiles = [
      ...activeUploadedFiles.map((f) => ({ name: f, isImage: false })),
      ...activeUploadedImages.map((img) => ({ name: img.split("/").pop(), path: img, isImage: true })),
    ];

    if (modalUploadedSection && modalUploadedGrid) {
      if (allFiles.length === 0) {
        modalUploadedSection.hidden = true;
        modalUploadedGrid.innerHTML = "";
      } else {
        modalUploadedSection.hidden = false;
        modalUploadedGrid.innerHTML = "";
        allFiles.forEach((item) => {
          modalUploadedGrid.appendChild(createUploadedCardElement(item));
        });
      }
    }

    if (emptyUploadedWrap && emptyUploadedList) {
      if (allFiles.length === 0) {
        emptyUploadedWrap.hidden = true;
        emptyUploadedList.innerHTML = "";
      } else {
        emptyUploadedWrap.hidden = false;
        emptyUploadedList.innerHTML = "";
        allFiles.forEach((item) => {
          emptyUploadedList.appendChild(createUploadedCardElement(item));
        });
      }
    }
  }


  // ================= SYSTEM STATUS (top pill) =================

  async function refreshHealth() {
    try {
      const health = await api("/api/health");
      const online = health.local_llm_online;
      llmStatusPill.classList.toggle("online", !!online);
      llmStatusPill.classList.toggle("offline", !online);
      llmStatusPill.innerHTML = `<span class="dot"></span> ${online ? "LOCAL AI ONLINE" : "LOCAL AI OFFLINE"}`;
      window._lastHealth = health;
    } catch (e) {
      llmStatusPill.classList.remove("online");
      llmStatusPill.classList.add("offline");
      llmStatusPill.innerHTML = `<span class="dot"></span> STATUS UNKNOWN`;
    }
  }

  // ================= CHAT: DEDICATED UPLOAD SECTION & MODAL =================

  function setUploadStatus(message, type = "") {
    [modalUploadStatus, emptyUploadStatus].forEach((el) => {
      if (!el) return;
      if (!message) {
        el.hidden = true;
        el.textContent = "";
        el.className = "dropzone-status-msg";
      } else {
        el.className = "dropzone-status-msg" + (type ? " " + type : "");
        el.textContent = message;
        el.hidden = false;
      }
    });
  }

  function openUploadModal() {
    setUploadStatus("");
    renderModalUploadedFiles();
    if (uploadModal) uploadModal.hidden = false;
  }

  function closeUploadModal() {
    if (uploadModal) uploadModal.hidden = true;
  }

  if (openUploadModalBtn) {
    openUploadModalBtn.addEventListener("click", openUploadModal);
  }
  if (closeUploadModalBtn) {
    closeUploadModalBtn.addEventListener("click", closeUploadModal);
  }
  if (uploadModal) {
    uploadModal.addEventListener("click", (e) => {
      if (e.target === uploadModal) closeUploadModal();
    });
  }

  if (browseModalFilesBtn && modalFileInput) {
    browseModalFilesBtn.addEventListener("click", () => modalFileInput.click());
  }

  if (emptyBrowseBtn && modalFileInput) {
    emptyBrowseBtn.addEventListener("click", () => modalFileInput.click());
  }

  if (modalFileInput) {
    modalFileInput.addEventListener("change", () => {
      const files = Array.from(modalFileInput.files || []);
      modalFileInput.value = "";
      if (files.length > 0) {
        handleIncomingUploadFiles(files);
      }
    });
  }

  // Setup drag and drop for modal dropzone and empty state dropzone
  [modalDropzone, emptyCardDropzone].forEach((dz) => {
    if (!dz) return;
    dz.addEventListener("click", (e) => {
      if (e.target.closest("button")) return;
      if (modalFileInput) modalFileInput.click();
    });
    ["dragover", "dragenter"].forEach((evt) => dz.addEventListener(evt, (e) => {
      e.preventDefault();
      dz.classList.add("dragover");
    }));
    ["dragleave", "drop"].forEach((evt) => dz.addEventListener(evt, (e) => {
      e.preventDefault();
      dz.classList.remove("dragover");
    }));
    dz.addEventListener("drop", (e) => {
      e.preventDefault();
      dz.classList.remove("dragover");
      const files = Array.from(e.dataTransfer.files || []);
      if (files.length > 0) {
        handleIncomingUploadFiles(files);
      }
    });
  });

  async function handleIncomingUploadFiles(files) {
    for (const file of files) {
      await uploadConversationFile(file);
    }
  }

  async function uploadConversationFile(file) {
    const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
    const docExtensions = [".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".csv", ".txt", ".md", ".text", ".log"];
    const imgExtensions = [".png", ".jpg", ".jpeg", ".webp"];
    const isDocument = docExtensions.includes(ext);
    const isImage = imgExtensions.includes(ext);

    if (!isDocument && !isImage) {
      const notice = `${file.name}: Unsupported format. Supported: PDF, DOCX, XLSX, CSV, PPTX, TXT, and Images (PNG, JPG, WEBP).`;
      setUploadStatus(notice, "error");
      return;
    }

    setUploadStatus(`Uploading & indexing ${file.name}...`);

    try {
      if (!currentConversationId) {
        await startNewChat();
      }

      const formData = new FormData();
      formData.append("file", file);
      if (currentConversationId) {
        formData.append("conversation_id", currentConversationId);
      }

      const res = await api("/api/upload", { method: "POST", body: formData });
      if (res.conversation_id && !currentConversationId) {
        currentConversationId = res.conversation_id;
      }

      if (isDocument) {
        if (!activeUploadedFiles.includes(file.name)) {
          activeUploadedFiles.push(file.name);
        }
      } else if (isImage) {
        const storedPath = res.filename || file.name;
        if (!activeUploadedImages.some((img) => img.endsWith(file.name))) {
          activeUploadedImages.push(storedPath);
        }
      }

      renderActiveAttachments();
      renderModalUploadedFiles();
      loadConversations();

      const statusMsg = res.indexed ? `\u2713 Uploaded & indexed: ${file.name}` : `\u2713 Uploaded: ${file.name}`;
      setUploadStatus(statusMsg, "success");
    } catch (err) {
      setUploadStatus(`Upload failed: ${err.message}`, "error");
    }
  }

  // Keyboard shortcut: Escape closes open modals and attachment popover
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeProfileModal();
      closeUploadModal();
      if (attachDropdown && !attachDropdown.hidden) {
        attachDropdown.hidden = true;
        if (attachMenuBtn) attachMenuBtn.setAttribute("aria-expanded", "false");
      }
    }
  });

  // ================= CHAT: ATTACHMENTS & DROPDOWN =================

  if (attachMenuBtn && attachDropdown) {
    attachMenuBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const isHidden = attachDropdown.hidden;
      attachDropdown.hidden = !isHidden;
      attachMenuBtn.setAttribute("aria-expanded", isHidden ? "true" : "false");
    });
  }

  // Close dropdown on click outside
  document.addEventListener("click", (e) => {
    if (attachWrapper && !attachWrapper.contains(e.target)) {
      if (attachDropdown && !attachDropdown.hidden) {
        attachDropdown.hidden = true;
        if (attachMenuBtn) attachMenuBtn.setAttribute("aria-expanded", "false");
      }
    }
  });

  // Dropdown menu options
  if (menuUploadFile) {
    menuUploadFile.addEventListener("click", () => {
      if (attachDropdown) attachDropdown.hidden = true;
      if (attachMenuBtn) attachMenuBtn.setAttribute("aria-expanded", "false");
      if (docFileInputUniversal) docFileInputUniversal.click();
      else if (pdfFileInput) pdfFileInput.click();
    });
  }

  if (menuUploadImage) {
    menuUploadImage.addEventListener("click", () => {
      if (attachDropdown) attachDropdown.hidden = true;
      if (attachMenuBtn) attachMenuBtn.setAttribute("aria-expanded", "false");
      if (imageFileInputUniversal) imageFileInputUniversal.click();
      else if (imageFileInput) imageFileInput.click();
    });
  }

  // Universal file inputs change handlers
  if (docFileInputUniversal) {
    docFileInputUniversal.addEventListener("change", async () => {
      const file = docFileInputUniversal.files[0];
      docFileInputUniversal.value = "";
      if (!file) return;
      await uploadConversationFile(file);
    });
  }

  if (imageFileInputUniversal) {
    imageFileInputUniversal.addEventListener("change", () => {
      const file = imageFileInputUniversal.files[0];
      imageFileInputUniversal.value = "";
      if (!file) return;
      pendingImage = file;
      renderPendingImageChip(file);
    });
  }

  // Legacy button fallbacks
  if (attachPdfBtn) {
    attachPdfBtn.addEventListener("click", () => {
      if (docFileInputUniversal) docFileInputUniversal.click();
      else if (pdfFileInput) pdfFileInput.click();
    });
  }
  if (attachImageBtn) {
    attachImageBtn.addEventListener("click", () => {
      if (imageFileInputUniversal) imageFileInputUniversal.click();
      else if (imageFileInput) imageFileInput.click();
    });
  }
  if (openUploadModalBtn) {
    openUploadModalBtn.addEventListener("click", openUploadModal);
  }

  pdfFileInput.addEventListener("change", async () => {
    const file = pdfFileInput.files[0];
    pdfFileInput.value = "";
    if (!file) return;
    await uploadConversationFile(file);
  });

  imageFileInput.addEventListener("change", () => {
    const file = imageFileInput.files[0];
    imageFileInput.value = "";
    if (!file) return;
    pendingImage = file;
    renderPendingImageChip(file);
  });

  // Suggestion card clicks on empty chat
  document.querySelectorAll(".suggestion-card").forEach((card) => {
    card.addEventListener("click", () => {
      const prompt = card.dataset.prompt;
      if (prompt && chatInput) {
        chatInput.value = prompt;
        chatInput.style.height = "auto";
        chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + "px";
        chatInput.focus();
      }
    });
  });

  function renderAttachmentChip(icon, name, statusText) {
    attachmentStrip.hidden = false;
    const card = document.createElement("div");
    card.className = "attachment-card";
    card.innerHTML = `<span class="att-icon">${icon}</span><div><div class="att-name">${escapeHtml(name)}</div><div class="att-status muted" style="font-size:11px;">${statusText}</div></div>`;
    attachmentStrip.appendChild(card);
    return card;
  }

  function renderPendingImageChip(file) {
    attachmentStrip.hidden = false;
    attachmentStrip.innerHTML = "";
    const card = document.createElement("div");
    card.className = "attachment-card";
    const url = URL.createObjectURL(file);
    card.innerHTML = `<img class="att-thumb" src="${url}" /><div class="att-name">${escapeHtml(file.name)}</div><button class="att-remove" title="Remove">\u00d7</button>`;
    card.querySelector(".att-remove").addEventListener("click", clearPendingImage);
    attachmentStrip.appendChild(card);
  }

  function clearPendingImage() {
    pendingImage = null;
    attachmentStrip.hidden = true;
    attachmentStrip.innerHTML = "";
  }

  // ================= CHAT: SEND =================

  chatInput.addEventListener("input", () => {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + "px";
  });

  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  sendBtn.addEventListener("click", sendMessage);

  // ================= AI RESPONSE MARKDOWN PARSER =================

  function formatInline(str) {
    if (!str) return "";
    let s = str;
    // Citations: [Source N] -> badge
    s = s.replace(/\[Source\s+(\d+)\]/gi, '<span class="citation">[Source $1]</span>');
    // Bold: **text** or __text__
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/__([^_]+)__/g, '<strong>$1</strong>');
    // Italic: *text* or _text_
    s = s.replace(/(^|[^\*])\*([^\*]+)\*([^\*]|$)/g, '$1<em>$2</em>$3');
    s = s.replace(/(^|[^_])_([^_]+)_([^_]|$)/g, '$1<em>$2</em>$3');
    // Strikethrough: ~~text~~
    s = s.replace(/~~([^~]+)~~/g, '<del>$1</del>');
    return s;
  }

  function formatAiResponse(text) {
    if (!text) return "";
    let raw = String(text);

    // 1. Extract and preserve fenced code blocks: ```lang ... ```
    const codeBlocks = [];
    raw = raw.replace(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g, (match, lang, code) => {
      const id = `__CODE_BLOCK_${codeBlocks.length}__`;
      const language = (lang || "").trim() || "text";
      const escapedCode = escapeHtml(code.trimEnd());
      const blockHtml = `<pre class="ai-code-block"><div class="ai-code-header"><span>${escapeHtml(language)}</span><button type="button" class="ai-copy-btn" onclick="navigator.clipboard.writeText(this.closest('.ai-code-block').querySelector('code').textContent);this.textContent='Copied!';setTimeout(()=>this.textContent='Copy',2000);">Copy</button></div><code>${escapedCode}</code></pre>`;
      codeBlocks.push(blockHtml);
      return `\n\n${id}\n\n`;
    });

    // 2. Extract and preserve inline code: `code`
    const inlineCodes = [];
    raw = raw.replace(/`([^`]+)`/g, (match, code) => {
      const id = `__INLINE_CODE_${inlineCodes.length}__`;
      inlineCodes.push(`<code class="ai-inline-code">${escapeHtml(code)}</code>`);
      return id;
    });

    // 3. Process line-by-line for block structure
    const lines = raw.split("\n");
    const output = [];
    let inList = null; // "ul" or "ol"
    let tableLines = [];

    function flushTable() {
      if (tableLines.length === 0) return;
      const rows = tableLines.map(line => {
        let trimmed = line.trim();
        if (trimmed.startsWith("|")) trimmed = trimmed.slice(1);
        if (trimmed.endsWith("|")) trimmed = trimmed.slice(0, -1);
        return trimmed.split("|").map(c => c.trim());
      });

      if (rows.length >= 2) {
        const isSep = (row) => row.every(c => /^:?-+:?$/.test(c.replace(/\s/g, "")));
        let headerRow = null;
        let dataRows = [];

        if (rows.length > 1 && isSep(rows[1])) {
          headerRow = rows[0];
          dataRows = rows.slice(2);
        } else {
          dataRows = rows;
        }

        let tableHtml = '<div class="ai-table-wrap"><table class="ai-table">';
        if (headerRow) {
          tableHtml += '<thead><tr>';
          headerRow.forEach(h => {
            tableHtml += `<th>${formatInline(h)}</th>`;
          });
          tableHtml += '</tr></thead>';
        }
        if (dataRows.length > 0) {
          tableHtml += '<tbody>';
          dataRows.forEach(r => {
            if (!isSep(r) && r.some(c => c.length > 0)) {
              tableHtml += '<tr>';
              r.forEach(cell => {
                tableHtml += `<td>${formatInline(cell)}</td>`;
              });
              tableHtml += '</tr>';
            }
          });
          tableHtml += '</tbody>';
        }
        tableHtml += '</table></div>';
        output.push(tableHtml);
      } else {
        tableLines.forEach(l => output.push(`<p class="ai-p">${formatInline(l)}</p>`));
      }
      tableLines = [];
    }

    function closeList() {
      if (inList) {
        output.push(`</${inList}>`);
        inList = null;
      }
    }

    for (let i = 0; i < lines.length; i++) {
      let line = lines[i];
      let trimmed = line.trim();

      // Check for markdown table
      if (/^\|(.+)\|$/.test(trimmed) || (trimmed.includes("|") && trimmed.split("|").length >= 3 && !trimmed.startsWith("```"))) {
        closeList();
        tableLines.push(trimmed);
        continue;
      } else if (tableLines.length > 0) {
        flushTable();
      }

      // Empty line
      if (!trimmed) {
        closeList();
        continue;
      }

      // Code block placeholder
      if (trimmed.startsWith("__CODE_BLOCK_") && trimmed.endsWith("__")) {
        closeList();
        output.push(trimmed);
        continue;
      }

      // Horizontal rule
      if (/^(\*{3,}|-{3,}|_{3,})$/.test(trimmed)) {
        closeList();
        output.push('<hr class="ai-hr" />');
        continue;
      }

      // Headings: # through ######
      const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
      if (headingMatch) {
        closeList();
        const level = headingMatch[1].length;
        const text = formatInline(headingMatch[2]);
        const tagClass = level === 1 ? "ai-h2" : level === 2 ? "ai-h3" : level === 3 ? "ai-h4" : level === 4 ? "ai-h5" : "ai-h6";
        output.push(`<div class="${tagClass}">${text}</div>`);
        continue;
      }

      // Blockquote: > ...
      const quoteMatch = trimmed.match(/^>\s*(.+)$/);
      if (quoteMatch) {
        closeList();
        output.push(`<blockquote class="ai-quote">${formatInline(quoteMatch[1])}</blockquote>`);
        continue;
      }

      // Unordered list: - item, * item, + item
      const ulMatch = trimmed.match(/^[\*\-\+]\s+(.+)$/);
      if (ulMatch) {
        if (inList !== "ul") {
          closeList();
          output.push('<ul class="ai-ul">');
          inList = "ul";
        }
        output.push(`<li class="ai-li">${formatInline(ulMatch[1])}</li>`);
        continue;
      }

      // Ordered list: 1. item, 2. item
      const olMatch = trimmed.match(/^\d+\.\s+(.+)$/);
      if (olMatch) {
        if (inList !== "ol") {
          closeList();
          output.push('<ol class="ai-ol">');
          inList = "ol";
        }
        output.push(`<li class="ai-li">${formatInline(olMatch[1])}</li>`);
        continue;
      }

      // Regular paragraph
      closeList();
      output.push(`<p class="ai-p">${formatInline(trimmed)}</p>`);
    }

    closeList();
    if (tableLines.length > 0) flushTable();

    let result = output.join("\n");

    // Restore inline code
    inlineCodes.forEach((codeHtml, idx) => {
      result = result.split(`__INLINE_CODE_${idx}__`).join(codeHtml);
    });

    // Restore code blocks
    codeBlocks.forEach((blockHtml, idx) => {
      result = result.split(`__CODE_BLOCK_${idx}__`).join(blockHtml);
    });

    return result;
  }

  function renderCitations(text) {
    return formatAiResponse(text);
  }

  function appendUserMessage(text, imageFile) {
    chatEmpty.style.display = "none";
    const row = document.createElement("div");
    row.className = "msg-row user";
    let attachmentHtml = "";
    if (imageFile) {
      attachmentHtml = `<div class="msg-attachment-chip">\uD83D\uDDBC ${escapeHtml(imageFile.name)}</div><br/>`;
    }
    row.innerHTML = `<div class="msg-bubble user">${attachmentHtml}${escapeHtml(text)}</div>`;
    messagesEl.appendChild(row);
    chatScroll.scrollTop = chatScroll.scrollHeight;
  }

  function appendThinkingRow() {
    const row = document.createElement("div");
    row.className = "msg-row ai";
    row.id = "thinkingRow";
    row.innerHTML = `<div class="thinking-row">AI is thinking <span class="thinking-dots"><span></span><span></span><span></span></span></div>`;
    messagesEl.appendChild(row);
    chatScroll.scrollTop = chatScroll.scrollHeight;
    return row;
  }

  window.toggleEvidence = function(id) {
    const list = document.getElementById(id);
    const chev = document.getElementById("chev_" + id);
    if (!list) return;
    const isExpanded = list.classList.toggle("expanded");
    if (chev) {
      chev.textContent = isExpanded ? "\u25b4" : "\u25be";
    }
  };

  function verificationBadge(verification) {
    if (!verification) return "";
    const status = verification.status || "UNKNOWN";
    if (status === "NO_DOCUMENT_CLAIMS") return "";

    let cls = "ok", label = "\u2713 Evidence Verified";

    if (status === "CITATION_MISMATCH") { cls = "bad"; label = "\u26a0 Evidence Verification Failed"; }
    else if (status === "MISSING_CITATION") { cls = "warn"; label = "\u26a0 Missing Evidence"; }
    else if (status === "CONTRADICTED") { cls = "bad"; label = "\u2715 Evidence Contradicted"; }
    else if (status === "SUPPORTED" || status === "SUMMARY_VERIFIED") { cls = "ok"; label = "\u2713 Evidence Verified"; }
    else if (!verification.verified) { cls = "warn"; label = "\u26a0 Needs Review"; }

    return `<div class="verify-badge ${cls}">${label}</div>`;
  }

  function evidencePanel(sources, verification, intent) {
    // Suppress evidence completely for image-only queries or when no sources exist
    if (intent === "image_only") return "";
    if (!sources || !Array.isArray(sources) || sources.length === 0) return "";

    const id = "ev_" + Math.random().toString(36).slice(2, 9);
    const badgeHtml = verificationBadge(verification);

    const cards = sources.map((s, idx) => {
      const isWeb = s.type === "global_web" || !!s.url;
      const srcTitle = s.title || s.source || (isWeb ? "Web Source" : "Document");
      const linkHtml = s.url
        ? `<div style="margin: 2px 0 4px;"><a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer" style="color:var(--accent-primary); font-size:11px; text-decoration:underline; word-break:break-all;">\uD83C\uDF10 ${escapeHtml(s.url)}</a></div>`
        : "";
      const metaInfo = isWeb
        ? `Global Web Source${s.score != null ? " \u00b7 Similarity: " + s.score.toFixed(2) : ""}`
        : `Page ${s.page != null ? s.page : 1}${s.score != null ? " \u00b7 Similarity: " + s.score.toFixed(2) : ""}`;

      return `
        <div class="evidence-card">
          <div class="evidence-source">[Source ${s.id != null ? s.id : (idx + 1)}] ${escapeHtml(srcTitle)}</div>
          ${linkHtml}
          <div class="evidence-meta">${metaInfo}</div>
          <div class="evidence-snippet">${escapeHtml((s.text || "").slice(0, 240))}${(s.text || "").length > 240 ? "\u2026" : ""}</div>
        </div>`;
    }).join("");

    return `
      <div class="evidence-panel" id="panel_${id}">
        <div class="evidence-header-bar" onclick="window.toggleEvidence('${id}')">
          <div class="evidence-status-wrap">
            ${badgeHtml}
          </div>
          <button type="button" class="evidence-toggle-btn" aria-label="Toggle evidence">
            <span>Evidence &amp; Sources (${sources.length})</span>
            <span class="evidence-chevron" id="chev_${id}">\u25be</span>
          </button>
        </div>
        <div class="evidence-list" id="${id}">${cards}</div>
      </div>`;
  }

  function renderAgentWorkflow(agentSteps, intent) {
    if (!agentSteps || !Array.isArray(agentSteps) || agentSteps.length === 0) return "";
    const stepsHtml = agentSteps.map((s) => {
      let label = escapeHtml(s);
      if (label.startsWith("Request classified as")) {
        label = "Request classified";
      }
      return `
        <div class="agent-step">
          <span class="agent-step-check">\u2713</span>
          <span>${label}</span>
        </div>
      `;
    }).join("");

    return `
      <div class="agent-workflow">
        <div class="agent-workflow-header">
          <span>\u2699 Agent Workflow</span>
        </div>
        ${stepsHtml}
      </div>`;
  }

  function appendAiMessage({ answer, sources, verification, imageObservation, model, executionTime, agentSteps, intent }) {
    const row = document.createElement("div");
    row.className = "msg-row ai";
    const modelLine = model ? `<span style="color:var(--text-muted); font-weight:500;"> \u00b7 ${escapeHtml(model)}${executionTime != null ? " \u00b7 " + executionTime + "s" : ""}</span>` : "";

    let imageObsHtml = "";
    if (imageObservation) {
      imageObsHtml = renderImageObservationInline(imageObservation);
    }
    const workflowHtml = renderAgentWorkflow(agentSteps, intent);

    // Collapsible evidence: only for queries with sources and non-image-only
    const isImageOnly = intent === "image_only";
    const evidenceHtml = isImageOnly ? "" : evidencePanel(sources, verification, intent);

    row.innerHTML = `
      <div class="msg-ai">
        <div class="msg-ai-label">SOVEREIGN AI${modelLine}</div>
        ${workflowHtml}
        ${imageObsHtml}
        <div class="msg-ai-body">${formatAiResponse(answer)}</div>
        ${evidenceHtml}
      </div>`;
    messagesEl.appendChild(row);
    chatScroll.scrollTop = chatScroll.scrollHeight;
  }

  function renderImageObservationInline(obs) {
    if (!obs || typeof obs !== "object") return "";
    const items = [];
    if (obs.image_type) items.push(`<span class="tag">${escapeHtml(obs.image_type)}</span>`);
    (obs.visible_damage || []).forEach((d) => items.push(`<span class="tag" style="border-color:var(--critical);color:var(--critical);">${escapeHtml(d)}</span>`));
    if (!items.length) return "";
    return `<div class="tag-list" style="margin-bottom:10px;">${items.join("")}</div>`;
  }

  function appendErrorMessage(text) {
    const row = document.createElement("div");
    row.className = "msg-row ai";
    row.innerHTML = `<div class="error-banner">${escapeHtml(text)}</div>`;
    messagesEl.appendChild(row);
    chatScroll.scrollTop = chatScroll.scrollHeight;
  }

  async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    const imageToSend = pendingImage;
    appendUserMessage(text, imageToSend);
    chatInput.value = "";
    chatInput.style.height = "auto";
    clearPendingImage();
    sendBtn.disabled = true;
    chatInput.disabled = true;

    const thinkingRow = appendThinkingRow();

    try {
      let data;
      if (imageToSend) {
        const formData = new FormData();
        formData.append("question", text);
        formData.append("image", imageToSend);
        formData.append("knowledge_mode", currentKnowledgeMode);
        if (currentConversationId) {
          formData.append("conversation_id", currentConversationId);
        }
        data = await api("/api/chat/multimodal", { method: "POST", body: formData });
      } else {
        const payload = {
          message: text,
          knowledge_mode: currentKnowledgeMode,
        };
        if (currentConversationId) {
          payload.conversation_id = currentConversationId;
        }
        data = await api("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      }
      thinkingRow.remove();

      if (data.conversation_id) {
        currentConversationId = data.conversation_id;
      }
      if (data.uploaded_files) {
        activeUploadedFiles = data.uploaded_files;
      }
      if (data.uploaded_images) {
        activeUploadedImages = data.uploaded_images;
      }
      if (data.global_sources) {
        activeGlobalSources = data.global_sources;
        renderGlobalSources();
      }
      renderActiveAttachments();
      renderModalUploadedFiles();
      loadConversations();

      appendAiMessage({
        answer: data.answer,
        sources: data.sources,
        verification: data.verification,
        imageObservation: data.image_observation,
        model: data.model,
        executionTime: data.execution_time,
        agentSteps: data.agent_steps,
        intent: data.intent,
      });
    } catch (err) {
      thinkingRow.remove();
      if (err.status === 422 && /no indexed documents/i.test(err.message)) {
        appendErrorMessage("The AI could not retrieve evidence from the local knowledge base. Upload and index documents first (Documents tab).");
      } else if (err.status === 500) {
        appendErrorMessage("Local AI service unavailable. Please start Ollama and try again.");
      } else if (err.status === 403) {
        appendErrorMessage(err.message || "You do not have permission to perform this action.");
      } else {
        appendErrorMessage(err.message || "Something went wrong.");
      }
    } finally {
      sendBtn.disabled = false;
      chatInput.disabled = false;
      chatInput.focus();
    }
  }

  // ================= DOCUMENTS =================

  const dropzone = document.getElementById("dropzone");
  const docFileInput = document.getElementById("docFileInput");
  const browseDocsBtn = document.getElementById("browseDocsBtn");
  const indexBtn = document.getElementById("indexBtn");
  const indexResultMsg = document.getElementById("indexResultMsg");
  const docsTableBody = document.getElementById("docsTableBody");
  const docsEmptyState = document.getElementById("docsEmptyState");

  browseDocsBtn.addEventListener("click", () => docFileInput.click());
  dropzone.addEventListener("click", (e) => { if (e.target === dropzone || dropzone.contains(e.target)) docFileInput.click(); });

  ["dragover", "dragenter"].forEach((evt) => dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach((evt) => dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.remove("dragover"); }));
  dropzone.addEventListener("drop", (e) => uploadDocFiles(Array.from(e.dataTransfer.files || [])));

  docFileInput.addEventListener("change", () => {
    uploadDocFiles(Array.from(docFileInput.files || []));
    docFileInput.value = "";
  });

  async function uploadDocFiles(files) {
    for (const file of files) {
      try {
        const formData = new FormData();
        formData.append("file", file);
        await api("/api/upload", { method: "POST", body: formData });
      } catch (err) {
        alert(`Upload failed for ${file.name}: ${err.message}`);
      }
    }
    loadDocuments();
  }

  indexBtn.addEventListener("click", async () => {
    indexBtn.disabled = true;
    indexResultMsg.textContent = "Indexing\u2026";
    try {
      const result = await api("/api/documents/index", { method: "POST" });
      if (result.indexed) {
        indexResultMsg.textContent = `\u2713 Indexed ${result.documents} document(s), ${result.chunks} chunks.`;
      } else {
        indexResultMsg.textContent = result.reason || "Nothing to index.";
      }
      loadDocuments();
    } catch (err) {
      indexResultMsg.textContent = "Indexing failed: " + err.message;
    } finally {
      indexBtn.disabled = false;
    }
  });

  async function loadDocuments() {
    try {
      const docs = await api("/api/documents");
      docsTableBody.innerHTML = "";
      docsEmptyState.hidden = docs.length !== 0;

      docs.forEach((doc) => {
        const tr = document.createElement("tr");
        const statusPill = doc.category === "image"
          ? `<span class="pill success">Ready</span>`
          : (doc.indexed ? `<span class="pill success">Indexed \u2713</span>` : `<span class="pill pending">Not indexed</span>`);

        tr.innerHTML = `
          <td>${doc.category === "image" ? "\uD83D\uDDBC" : "\uD83D\uDCC4"} ${escapeHtml(doc.filename)}</td>
          <td>${doc.category === "image" ? "Image" : "PDF"}</td>
          <td>${formatSize(doc.size_bytes)}</td>
          <td>${statusPill}</td>
          <td>${doc.pages != null ? doc.pages : "\u2014"}</td>
          <td>${doc.chunks != null ? doc.chunks : "\u2014"}</td>
          <td><button class="icon-btn-danger" data-id="${doc.id}">Delete</button></td>
        `;
        tr.querySelector(".icon-btn-danger").addEventListener("click", () => deleteDocument(doc.id));
        docsTableBody.appendChild(tr);
      });
    } catch (err) {
      // non-fatal; leave table as-is
    }
  }

  async function deleteDocument(id) {
    if (!confirm("Delete this file?")) return;
    try {
      await api("/api/documents/" + id, { method: "DELETE" });
      loadDocuments();
    } catch (err) {
      alert("Delete failed: " + err.message);
    }
  }

  // ================= VISION =================

  const visionDropzone = document.getElementById("visionDropzone");
  const visionFileInput = document.getElementById("visionFileInput");
  const browseVisionBtn = document.getElementById("browseVisionBtn");
  const visionPreviewWrap = document.getElementById("visionPreviewWrap");
  const visionPreviewImg = document.getElementById("visionPreviewImg");
  const analyzeVisionBtn = document.getElementById("analyzeVisionBtn");
  const visionResultPanel = document.getElementById("visionResultPanel");
  const visionResultBody = document.getElementById("visionResultBody");

  let visionFile = null;

  browseVisionBtn.addEventListener("click", () => visionFileInput.click());
  visionDropzone.addEventListener("click", (e) => { if (e.target === visionDropzone || visionDropzone.contains(e.target)) visionFileInput.click(); });
  ["dragover", "dragenter"].forEach((evt) => visionDropzone.addEventListener(evt, (e) => { e.preventDefault(); visionDropzone.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach((evt) => visionDropzone.addEventListener(evt, (e) => { e.preventDefault(); visionDropzone.classList.remove("dragover"); }));
  visionDropzone.addEventListener("drop", (e) => { const f = e.dataTransfer.files[0]; if (f) setVisionFile(f); });
  visionFileInput.addEventListener("change", () => { if (visionFileInput.files[0]) setVisionFile(visionFileInput.files[0]); });

  function setVisionFile(file) {
    visionFile = file;
    visionPreviewImg.src = URL.createObjectURL(file);
    visionPreviewWrap.hidden = false;
    visionResultPanel.hidden = true;
  }

  analyzeVisionBtn.addEventListener("click", async () => {
    if (!visionFile) return;
    analyzeVisionBtn.disabled = true;
    analyzeVisionBtn.textContent = "Analyzing\u2026";
    try {
      const formData = new FormData();
      formData.append("image", visionFile);
      const data = await api("/api/vision/analyze", { method: "POST", body: formData });
      renderVisionResult(data.result, data.model, data.execution_time);
    } catch (err) {
      visionResultPanel.hidden = false;
      visionResultBody.innerHTML = `<div class="error-banner">${escapeHtml(err.message || "Analysis failed.")}</div>`;
    } finally {
      analyzeVisionBtn.disabled = false;
      analyzeVisionBtn.textContent = "Analyze Image";
    }
  });

  function tagListHtml(items) {
    if (!items || items.length === 0) return `<span class="muted">None detected</span>`;
    return `<div class="tag-list">${items.map((i) => `<span class="tag">${escapeHtml(String(i))}</span>`).join("")}</div>`;
  }

  function renderVisionResult(result, model, executionTime) {
    visionResultPanel.hidden = false;
    const confidence = typeof result.confidence === "number" ? Math.round(result.confidence * 100) + "%" : "\u2014";

    visionResultBody.innerHTML = `
      <div class="vision-field"><div class="vision-field-label">Object / Image Type</div><div class="vision-field-value">${escapeHtml(result.image_type || "Unknown")}</div></div>
      <div class="vision-field"><div class="vision-field-label">Components</div>${tagListHtml(result.visible_components)}</div>
      <div class="vision-field"><div class="vision-field-label">Equipment</div>${tagListHtml(result.visible_equipment)}</div>
      <div class="vision-field"><div class="vision-field-label">Visible Text</div>${tagListHtml(result.visible_text)}</div>
      <div class="vision-field"><div class="vision-field-label">Conditions</div>${tagListHtml(result.visible_conditions)}</div>
      <div class="vision-field"><div class="vision-field-label">Visible Damage</div>${tagListHtml(result.visible_damage)}</div>
      <div class="vision-field"><div class="vision-field-label">Abnormalities</div>${tagListHtml(result.abnormalities)}</div>
      <div class="vision-field"><div class="vision-field-label">Confidence</div><div class="vision-field-value">${confidence}</div></div>
      <div class="muted" style="margin-top:10px; font-size:11.5px;">${escapeHtml(model || "")} \u00b7 ${executionTime != null ? executionTime + "s" : ""}</div>
    `;
  }

  // ================= AUDIT =================

  const auditTableBody = document.getElementById("auditTableBody");
  const auditEmptyState = document.getElementById("auditEmptyState");

  async function loadAudit() {
    try {
      const events = await api("/api/audit");
      auditTableBody.innerHTML = "";
      auditEmptyState.hidden = events.length !== 0;

      events.forEach((ev) => {
        const tr = document.createElement("tr");
        const statusClass = /SUCCESS|SUPPORTED|VERIFIED|NO_DOCUMENT/i.test(ev.status || "") ? "success" : (/FAIL|DENIED|MISMATCH|CONTRADICT/i.test(ev.status || "") ? "" : "pending");
        tr.innerHTML = `
          <td>${formatTimestamp(ev.timestamp)}</td>
          <td>${escapeHtml(ev.user || "")}</td>
          <td>${escapeHtml(ev.action || "")}</td>
          <td><span class="pill ${statusClass}">${escapeHtml(ev.status || "")}</span></td>
          <td class="muted">${escapeHtml(ev.details || "")}</td>
        `;
        auditTableBody.appendChild(tr);
      });
    } catch (err) {
      // non-fatal
    }
  }

  // ================= SYSTEM STATUS PAGE =================

  const statusGrid = document.getElementById("statusGrid");

  async function loadStatus() {
    statusGrid.innerHTML = `<div class="muted">Checking local AI stack\u2026</div>`;
    try {
      const health = await api("/api/health");
      const cards = [
        ["Local LLM", health.local_llm_online],
        ["Vision Model", health.vision_model_online],
        ["Embeddings", health.embeddings_loaded],
        ["FAISS", health.faiss_ready],
        ["RAG", health.rag_ready],
        ["Evidence Checker", health.evidence_checker_ready],
      ];
      statusGrid.innerHTML = cards.map(([label, online]) => `
        <div class="status-card">
          <div class="status-card-label">${label}</div>
          <div class="status-card-value ${online ? "online" : "offline"}"><span class="dot"></span>${online ? "Online" : "Offline"}</div>
        </div>`).join("") + `
        <div class="status-card">
          <div class="status-card-label">Network</div>
          <div class="status-card-value"><span class="dot" style="background:var(--text-muted);"></span>${escapeHtml(health.network)}</div>
        </div>`;
    } catch (err) {
      statusGrid.innerHTML = `<div class="error-banner">Could not reach the backend: ${escapeHtml(err.message)}</div>`;
    }
  }

  // ================= ADMIN PANEL DASHBOARD =================

  let currentAdminTab = "pending";

  function switchAdminTab(tabName) {
    currentAdminTab = tabName;
    document.querySelectorAll(".admin-tab-btn").forEach((b) => {
      b.classList.toggle("active", b.dataset.adminTab === tabName);
    });
    if (adminTabPending) adminTabPending.classList.toggle("hidden", tabName !== "pending");
    if (adminTabUsers) adminTabUsers.classList.toggle("hidden", tabName !== "users");
    if (adminTabAudit) adminTabAudit.classList.toggle("hidden", tabName !== "audit");

    if (tabName === "pending") loadAdminPending();
    if (tabName === "users") loadAdminUsers();
    if (tabName === "audit") loadAdminAudit();
  }

  if (adminTabPendingBtn) adminTabPendingBtn.addEventListener("click", () => switchAdminTab("pending"));
  if (adminTabUsersBtn) adminTabUsersBtn.addEventListener("click", () => switchAdminTab("users"));
  if (adminTabAuditBtn) adminTabAuditBtn.addEventListener("click", () => switchAdminTab("audit"));
  if (adminRefreshBtn) adminRefreshBtn.addEventListener("click", () => loadAdminDashboard());

  async function loadAdminDashboard() {
    await loadAdminStats();
    if (currentAdminTab === "pending") await loadAdminPending();
    else if (currentAdminTab === "users") await loadAdminUsers();
    else if (currentAdminTab === "audit") await loadAdminAudit();
  }

  async function loadAdminStats() {
    try {
      const stats = await api("/api/admin/stats");
      if (statTotalUsers) statTotalUsers.textContent = stats.total_users || 0;
      if (statPending) statPending.textContent = stats.pending || 0;
      if (statApproved) statApproved.textContent = stats.approved || 0;
      if (statActive) statActive.textContent = stats.active || 0;
      if (statDisabled) statDisabled.textContent = stats.disabled || 0;
      if (statEmployees) statEmployees.textContent = stats.employees || 0;
      if (statOperators) statOperators.textContent = stats.operators || 0;
      if (statAdmins) statAdmins.textContent = stats.admins || 0;

      if (tabPendingBadge) {
        if (stats.pending > 0) {
          tabPendingBadge.textContent = stats.pending;
          tabPendingBadge.hidden = false;
        } else {
          tabPendingBadge.hidden = true;
        }
      }
    } catch (e) {
      // non-fatal
    }
  }

  async function loadAdminPending() {
    if (!adminPendingTableBody) return;
    try {
      const list = await api("/api/admin/pending");
      adminPendingTableBody.innerHTML = "";
      if (adminPendingEmpty) adminPendingEmpty.hidden = (list && list.length > 0);

      if (!list || list.length === 0) return;

      list.forEach((u) => {
        const tr = document.createElement("tr");
        const rolePill = `<span class="pill pending">${escapeHtml(u.role || "")}</span>`;
        const statusPill = `<span class="pill pending">Pending Approval</span>`;

        tr.innerHTML = `
          <td><strong>${escapeHtml(u.name || u.username)}</strong></td>
          <td><code>${escapeHtml(u.username)}</code></td>
          <td>${escapeHtml(u.mobile || "\u2014")}</td>
          <td>${rolePill}</td>
          <td>${escapeHtml(u.company || "")}</td>
          <td class="muted">${formatTimestamp(u.created_at)}</td>
          <td>${statusPill}</td>
          <td>
            <div class="btn-action-group">
              <button type="button" class="btn-sm btn-approve" data-id="${u.id}" data-user="${escapeHtml(u.username)}">Approve</button>
              <button type="button" class="btn-sm btn-reject" data-id="${u.id}" data-user="${escapeHtml(u.username)}">Reject</button>
            </div>
          </td>
        `;

        tr.querySelector(".btn-approve").addEventListener("click", () => approveUser(u.id, u.username));
        tr.querySelector(".btn-reject").addEventListener("click", () => rejectUser(u.id, u.username));
        adminPendingTableBody.appendChild(tr);
      });
    } catch (e) {
      // non-fatal
    }
  }

  async function loadAdminUsers() {
    if (!adminUsersTableBody) return;
    try {
      const rawList = await api("/api/admin/users");
      const list = (rawList || []).filter((u) => (u.status || "").toUpperCase() !== "DELETED");
      adminUsersTableBody.innerHTML = "";
      if (adminUsersEmpty) adminUsersEmpty.hidden = (list && list.length > 0);

      if (!list || list.length === 0) return;

      list.forEach((u) => {
        const tr = document.createElement("tr");
        const st = (u.status || "APPROVED").toUpperCase();
        let stClass = "pending";
        if (st === "APPROVED") stClass = "success";
        else if (st === "DISABLED" || st === "REJECTED" || st === "DELETED") stClass = "bad";

        const isSelf = currentUser && currentUser.username === u.username;

        let actionButtonsHtml = "";
        if (st === "PENDING") {
          actionButtonsHtml += `<button type="button" class="btn-sm btn-approve" data-action="approve">Approve</button>`;
          actionButtonsHtml += `<button type="button" class="btn-sm btn-reject" data-action="reject">Reject</button>`;
        } else if (st === "APPROVED") {
          actionButtonsHtml += `<button type="button" class="btn-sm btn-disable" data-action="disable" ${isSelf ? "disabled title='Cannot disable self'" : ""}>Disable</button>`;
        } else if (st === "DISABLED") {
          actionButtonsHtml += `<button type="button" class="btn-sm btn-enable" data-action="enable">Enable</button>`;
        }

        actionButtonsHtml += `<button type="button" class="btn-sm btn-remove" data-action="delete" ${isSelf ? "disabled title='Cannot delete self'" : ""}>Remove</button>`;

        tr.innerHTML = `
          <td><strong>${escapeHtml(u.name || u.username)}</strong></td>
          <td><code>${escapeHtml(u.username)}</code></td>
          <td><span class="pill ${u.role === "admin" ? "success" : ""}">${escapeHtml(u.role || "")}</span></td>
          <td>${escapeHtml(u.company || "")}</td>
          <td><span class="pill ${stClass}">${escapeHtml(st)}</span></td>
          <td class="muted">${formatTimestamp(u.created_at)}</td>
          <td class="muted">${u.last_login_at ? formatTimestamp(u.last_login_at) : "Never"}</td>
          <td class="muted">${escapeHtml(u.approved_by || "\u2014")}</td>
          <td>
            <div class="btn-action-group">
              ${actionButtonsHtml}
            </div>
          </td>
        `;

        const btnApprove = tr.querySelector('[data-action="approve"]');
        if (btnApprove) btnApprove.addEventListener("click", () => approveUser(u.id, u.username));

        const btnReject = tr.querySelector('[data-action="reject"]');
        if (btnReject) btnReject.addEventListener("click", () => rejectUser(u.id, u.username));

        const btnDisable = tr.querySelector('[data-action="disable"]');
        if (btnDisable) btnDisable.addEventListener("click", () => disableUser(u.id, u.username));

        const btnEnable = tr.querySelector('[data-action="enable"]');
        if (btnEnable) btnEnable.addEventListener("click", () => enableUser(u.id, u.username));

        const btnDelete = tr.querySelector('[data-action="delete"]');
        if (btnDelete) btnDelete.addEventListener("click", () => deleteUser(u.id, u.username, u.role));

        adminUsersTableBody.appendChild(tr);
      });
    } catch (e) {
      // non-fatal
    }
  }

  async function loadAdminAudit() {
    if (!adminAuditTableBody) return;
    try {
      const events = await api("/api/admin/audit");
      adminAuditTableBody.innerHTML = "";
      if (adminAuditEmpty) adminAuditEmpty.hidden = (events && events.length > 0);

      if (!events || events.length === 0) return;

      events.forEach((ev) => {
        const tr = document.createElement("tr");
        const statusClass = /SUCCESS|SUPPORTED|VERIFIED/i.test(ev.status || "") ? "success" : (/FAIL|DENIED|REJECT|DISABLED/i.test(ev.status || "") ? "bad" : "pending");

        tr.innerHTML = `
          <td class="muted" style="white-space:nowrap;">${formatTimestamp(ev.timestamp)}</td>
          <td><strong>${escapeHtml(ev.user || "")}</strong></td>
          <td><span class="pill ${ev.role === "admin" ? "success" : ""}">${escapeHtml(ev.role || "\u2014")}</span></td>
          <td>${escapeHtml(ev.company || "")}</td>
          <td><code>${escapeHtml(ev.action || "")}</code></td>
          <td>${escapeHtml(ev.target || "\u2014")}</td>
          <td><span class="pill ${statusClass}">${escapeHtml(ev.status || "")}</span></td>
          <td class="muted" style="max-width:320px; word-break:break-word;">${escapeHtml(ev.details || "")}</td>
        `;
        adminAuditTableBody.appendChild(tr);
      });
    } catch (e) {
      // non-fatal
    }
  }

  // ================= ADMIN ACTIONS =================

  async function approveUser(id, username) {
    try {
      const res = await api(`/api/admin/users/${id}/approve`, { method: "POST" });
      await loadAdminDashboard();
    } catch (err) {
      alert("Approval failed: " + err.message);
    }
  }

  async function rejectUser(id, username) {
    if (!confirm(`Are you sure you want to reject registration for '${username}'?`)) return;
    try {
      const res = await api(`/api/admin/users/${id}/reject`, { method: "POST" });
      await loadAdminDashboard();
    } catch (err) {
      alert("Rejection failed: " + err.message);
    }
  }

  async function disableUser(id, username) {
    if (!confirm(`Are you sure you want to disable account for user '${username}'?`)) return;
    try {
      const res = await api(`/api/admin/users/${id}/disable`, { method: "POST" });
      await loadAdminDashboard();
    } catch (err) {
      alert("Disable failed: " + err.message);
    }
  }

  async function enableUser(id, username) {
    try {
      const res = await api(`/api/admin/users/${id}/enable`, { method: "POST" });
      await loadAdminDashboard();
    } catch (err) {
      alert("Enable failed: " + err.message);
    }
  }

  async function deleteUser(id, username, role) {
    const roleLabel = role || "user";
    if (!confirm(`Are you sure you want to permanently remove ${roleLabel} '${username}'? This action cannot be undone.`)) return;
    try {
      const res = await api(`/api/admin/users/${id}`, { method: "DELETE" });
      await loadAdminDashboard();
    } catch (err) {
      alert("Remove failed: " + err.message);
    }
  }

  // ================= INIT =================

  // Always show landing screen with SIGN IN and REGISTER options when page loads
  loginScreen.hidden = false;
  appShell.hidden = true;
  showLanding();
})();