const API_BASE = localStorage.getItem("opspilot_api_base") || "http://localhost:8080";
const ACTOR_ID = "web-console";
const navItems = [
  ["dashboard", "Dashboard"],
  ["identity", "Identity"],
  ["projects", "Projects"],
  ["assets", "Assets"],
  ["environments", "Environments"],
];

const state = {
  route: "dashboard",
  query: "",
  filters: {},
  apiOnline: false,
  user: sessionStorage.getItem("opspilot_user") || "",
  users: [],
  projects: [],
  assets: [],
  environments: [],
  auditEvents: [],
};

const seed = {
  users: [
    { id: "usr_mock_admin", name: "Lin Chen", email: "lin.chen@opspilot.local", status: "active", roles: [{ scope: "platform", name: "Admin" }], updated_at: "2026-06-04T07:18:00Z" },
    { id: "usr_mock_ops", name: "Maya Rao", email: "maya.rao@opspilot.local", status: "active", roles: [{ scope: "project", name: "Operator" }], updated_at: "2026-06-04T07:19:00Z" },
    { id: "usr_mock_view", name: "Jon Bell", email: "jon.bell@opspilot.local", status: "inactive", roles: [{ scope: "project", name: "Viewer" }], updated_at: "2026-06-04T07:20:00Z" },
  ],
  projects: [
    { id: "prj_mock_core", key: "OPS", name: "OpsPilot Core", description: "Foundation inventory and agent operations.", owner_id: "usr_mock_admin", member_ids: ["usr_mock_admin", "usr_mock_ops"], asset_ids: ["ast_mock_ws", "ast_mock_gpu"], environment_ids: ["env_mock_dev", "env_mock_qa"], status: "active", updated_at: "2026-06-04T07:21:00Z" },
    { id: "prj_mock_lab", key: "LAB", name: "Automation Lab", description: "Sandbox for environment readiness testing.", owner_id: "usr_mock_ops", member_ids: ["usr_mock_ops"], asset_ids: ["ast_mock_vm"], environment_ids: ["env_mock_qe"], status: "active", updated_at: "2026-06-04T07:22:00Z" },
  ],
  assets: [
    { id: "ast_mock_ws", category: "workstation", name: "Shanghai Workstation 01", status: "in_use", owner_id: "usr_mock_admin", location: "Shanghai Lab A", parent_id: "", capabilities: ["cuda", "local-build"], properties: { cpu: "Ryzen 7950X", memory: "128GB" }, updated_at: "2026-06-04T07:21:30Z" },
    { id: "ast_mock_gpu", category: "gpu", name: "RTX 4090 Slot A", status: "in_use", owner_id: "usr_mock_admin", location: "Shanghai Lab A", parent_id: "ast_mock_ws", capabilities: ["cuda", "24gb-vram"], properties: { vram: "24GB" }, updated_at: "2026-06-04T07:21:40Z" },
    { id: "ast_mock_vm", category: "vm", name: "qa-runner-03", status: "available", owner_id: "usr_mock_ops", location: "10.40.7.13", parent_id: "", capabilities: ["linux", "test-runner"], properties: { os: "Ubuntu 24.04" }, updated_at: "2026-06-04T07:22:30Z" },
  ],
  environments: [
    { id: "env_mock_dev", project_id: "prj_mock_core", name: "Core DEV", type: "DEV", status: "active", owner_id: "usr_mock_admin", member_ids: ["usr_mock_admin"], asset_ids: ["ast_mock_ws"], endpoints: [{ name: "api", url: "http://dev.opspilot.local" }], updated_at: "2026-06-04T07:23:00Z" },
    { id: "env_mock_qa", project_id: "prj_mock_core", name: "Core QA", type: "QA", status: "active", owner_id: "usr_mock_ops", member_ids: ["usr_mock_ops"], asset_ids: ["ast_mock_vm"], endpoints: [], updated_at: "2026-06-04T07:23:30Z" },
    { id: "env_mock_qe", project_id: "prj_mock_lab", name: "Lab QE", type: "QE", status: "inactive", owner_id: "usr_mock_ops", member_ids: [], asset_ids: [], endpoints: [], updated_at: "2026-06-04T07:24:00Z" },
  ],
  auditEvents: [
    { id: "aud_mock_1", actor_id: "system", action: "project.created", resource_type: "project", resource_id: "prj_mock_core", occurred_at: "2026-06-04T07:21:00Z", metadata: { key: "OPS" } },
    { id: "aud_mock_2", actor_id: "system", action: "asset.created", resource_type: "asset", resource_id: "ast_mock_gpu", occurred_at: "2026-06-04T07:21:40Z", metadata: { category: "gpu" } },
    { id: "aud_mock_3", actor_id: "system", action: "environment.created", resource_type: "environment", resource_id: "env_mock_qa", occurred_at: "2026-06-04T07:23:30Z", metadata: { type: "QA" } },
  ],
};

const $ = (selector) => document.querySelector(selector);
const content = $("#content");
const modal = $("#modal");

document.addEventListener("DOMContentLoaded", () => {
  $("#login-form").addEventListener("submit", signIn);
  $("#sign-out").addEventListener("click", signOut);
  $("#modal-close").addEventListener("click", () => modal.close());
  $("#refresh").addEventListener("click", () => loadData(true));
  $("#global-search").addEventListener("input", (event) => {
    state.query = event.target.value.trim().toLowerCase();
    render();
  });
  renderNav();
  if (state.user) showApp();
});

async function signIn(event) {
  event.preventDefault();
  state.user = $("#login-email").value.trim();
  sessionStorage.setItem("opspilot_user", state.user);
  showApp();
}

function signOut() {
  sessionStorage.removeItem("opspilot_user");
  state.user = "";
  $("#app").classList.add("hidden");
  $("#login").classList.remove("hidden");
}

function showApp() {
  $("#login").classList.add("hidden");
  $("#app").classList.remove("hidden");
  loadData();
}

async function loadData(forceToast = false) {
  try {
    const [users, projects, assets, environments, auditEvents] = await Promise.all([
      apiGet("/v1/users"),
      apiGet("/v1/projects"),
      apiGet("/v1/assets"),
      apiGet("/v1/environments"),
      apiGet("/v1/audit-events"),
    ]);
    state.apiOnline = true;
    state.users = users.length ? users : seed.users;
    state.projects = projects.length ? projects : seed.projects;
    state.assets = assets.length ? assets : seed.assets;
    state.environments = environments.length ? environments : seed.environments;
    state.auditEvents = auditEvents.length ? auditEvents : seed.auditEvents;
    if (forceToast) toast("Foundation API data refreshed.");
  } catch (error) {
    state.apiOnline = false;
    Object.assign(state, structuredClone(seed));
    if (forceToast) toast("Using local mock inventory because the API is unavailable.");
  }
  render();
}

async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) throw new Error(path);
  return response.json();
}

async function apiPost(path, payload) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Actor-ID": ACTOR_ID },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({ error: "request_failed" }));
    throw new Error(data.error || "request_failed");
  }
  return response.json();
}

function renderNav() {
  $("#nav").innerHTML = navItems.map(([key, label]) => `<button data-route="${key}"><span>${label}</span><small>${countFor(key)}</small></button>`).join("");
  $("#nav").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-route]");
    if (!button) return;
    state.route = button.dataset.route;
    state.filters = {};
    render();
  });
}

function render() {
  $("#api-state").textContent = state.apiOnline ? "Foundation API live" : "Local mock mode";
  $(".status-dot").classList.toggle("live", state.apiOnline);
  $("#project-switcher").innerHTML = `<option>All projects</option>${state.projects.map((p) => `<option>${escapeHtml(p.key)} · ${escapeHtml(p.name)}</option>`).join("")}`;
  document.querySelectorAll("#nav button").forEach((button) => button.classList.toggle("active", button.dataset.route === state.route));
  if (state.route === "dashboard") renderDashboard();
  if (state.route === "identity") renderResource("identity");
  if (state.route === "projects") renderResource("projects");
  if (state.route === "assets") renderResource("assets");
  if (state.route === "environments") renderResource("environments");
}

function renderDashboard() {
  const readinessIssues = state.environments.filter((env) => readiness(env).level !== "ok");
  content.innerHTML = `
    <div class="page-head">
      <div>
        <p class="eyebrow">Authenticated shell</p>
        <h1>Inventory command center</h1>
        <p class="muted">Dense setup status for identity, projects, assets, and environment readiness.</p>
      </div>
      <button class="primary-button" data-action="create-project">Create project</button>
    </div>
    <div class="metric-grid">
      ${metric("Users", state.users.length, `${activeCount(state.users)} active identities`)}
      ${metric("Projects", state.projects.length, `${linkedProjects()} with inventory links`)}
      ${metric("Assets", state.assets.length, `${state.assets.filter((a) => a.parent_id).length} installed components`)}
      ${metric("Environments", state.environments.length, `${readinessIssues.length} readiness warnings`)}
    </div>
    <div class="setup-grid">
      ${setupCard("Identity", state.users.length > 0, "Users and platform roles are available.")}
      ${setupCard("Projects", state.projects.every((p) => p.owner_id), "Project owners and member references are recorded.")}
      ${setupCard("Assets", state.assets.some((a) => a.capabilities?.length), "Capability-tagged inventory exists for allocation.")}
      ${setupCard("Environments", readinessIssues.length === 0, readinessIssues.length ? "Some environments need owners, assets, or endpoints." : "All environments are ready.")}
    </div>
    <div class="detail-grid">
      <section class="detail-panel">
        <h2>Inventory exceptions</h2>
        ${readinessIssues.length ? `<ul class="link-list">${readinessIssues.map((env) => `<li><strong>${escapeHtml(env.name)}</strong><br><span class="muted">${readiness(env).message}</span></li>`).join("")}</ul>` : `<div class="empty-state">No readiness exceptions.</div>`}
      </section>
      <section class="detail-panel">
        <h2>Recent audit</h2>
        ${activityList(state.auditEvents.slice(0, 6))}
      </section>
    </div>
  `;
  content.querySelector("[data-action='create-project']").addEventListener("click", () => openCreate("projects"));
}

function renderResource(type) {
  const config = resourceConfig(type);
  const rows = filteredRows(type);
  content.innerHTML = `
    <div class="page-head">
      <div>
        <p class="eyebrow">${config.eyebrow}</p>
        <h1>${config.title}</h1>
        <p class="muted">${config.copy}</p>
      </div>
      <button class="primary-button" data-create="${type}">${config.action}</button>
    </div>
    <div class="toolbar">
      <label>Search this view<input data-filter="localQuery" type="search" value="${escapeHtml(state.filters.localQuery || "")}" placeholder="${config.search}" /></label>
      ${config.filters.map((filter) => filterControl(filter)).join("")}
      <label>Rows<select data-filter="limit"><option>10</option><option ${state.filters.limit === "25" ? "selected" : ""}>25</option></select></label>
      <button class="ghost-button" data-clear>Clear</button>
    </div>
    <section class="table-wrap" aria-label="${config.title} table">
      ${rows.length ? tableFor(type, rows) : `<div class="empty-state">No ${config.title.toLowerCase()} match the current filters.</div>`}
    </section>
    <section id="detail-slot"></section>
  `;
  bindToolbar(type);
  content.querySelector("[data-create]").addEventListener("click", () => openCreate(type));
  content.querySelectorAll("[data-open]").forEach((button) => button.addEventListener("click", () => renderDetail(type, button.dataset.open)));
}

function resourceConfig(type) {
  return {
    identity: {
      eyebrow: "RBAC baseline",
      title: "Identity",
      copy: "Users, status, and scoped roles used by project and environment ownership.",
      action: "Create user",
      search: "Name, email, role",
      filters: [{ key: "status", label: "Status", values: ["all", "active", "inactive"] }],
    },
    projects: {
      eyebrow: "Project inventory",
      title: "Projects",
      copy: "Project records with owner, members, linked environments, assets, and activity.",
      action: "Create project",
      search: "Name, key, owner",
      filters: [{ key: "status", label: "Status", values: ["all", "active", "archived"] }],
    },
    assets: {
      eyebrow: "Asset hierarchy",
      title: "Assets",
      copy: "Physical and virtual inventory with category fields, capabilities, and parent-child links.",
      action: "Register asset",
      search: "Name, category, location",
      filters: [
        { key: "category", label: "Category", values: ["all", "server", "workstation", "vm", "gpu", "memory"] },
        { key: "status", label: "Status", values: ["all", "available", "in_use", "maintenance", "retired"] },
      ],
    },
    environments: {
      eyebrow: "Environment readiness",
      title: "Environments",
      copy: "DEV, QA, and QE environments with owners, endpoints, members, and inventory bindings.",
      action: "Create environment",
      search: "Name, project, owner",
      filters: [
        { key: "type", label: "Type", values: ["all", "DEV", "QA", "QE"] },
        { key: "readiness", label: "Readiness", values: ["all", "ready", "warning"] },
      ],
    },
  }[type];
}

function filteredRows(type) {
  const map = { identity: state.users, projects: state.projects, assets: state.assets, environments: state.environments };
  const query = [state.query, state.filters.localQuery].filter(Boolean).join(" ").toLowerCase();
  return map[type].filter((row) => {
    const text = JSON.stringify(row).toLowerCase();
    if (query && !query.split(/\s+/).every((token) => text.includes(token))) return false;
    if (type === "assets" && state.filters.category && state.filters.category !== "all" && row.category !== state.filters.category) return false;
    if ((type === "identity" || type === "projects" || type === "assets") && state.filters.status && state.filters.status !== "all" && row.status !== state.filters.status) return false;
    if (type === "environments" && state.filters.type && state.filters.type !== "all" && row.type !== state.filters.type) return false;
    if (type === "environments" && state.filters.readiness && state.filters.readiness !== "all") {
      const ready = readiness(row).level === "ok" ? "ready" : "warning";
      if (ready !== state.filters.readiness) return false;
    }
    return true;
  }).slice(0, Number(state.filters.limit || 10));
}

function tableFor(type, rows) {
  const headers = {
    identity: ["User", "Status", "Roles", "Updated"],
    projects: ["Project", "Owner", "Members", "Links", "Status"],
    assets: ["Asset", "Category", "Owner", "Location", "Status", "Capabilities"],
    environments: ["Environment", "Project", "Owner", "Bindings", "Readiness"],
  }[type];
  return `<table><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => rowFor(type, row)).join("")}</tbody></table>`;
}

function rowFor(type, row) {
  if (type === "identity") return `<tr><td>${titleCell(row.id, row.name, row.email)}</td><td>${statusPill(row.status)}</td><td>${roles(row.roles)}</td><td>${date(row.updated_at)}</td></tr>`;
  if (type === "projects") return `<tr><td>${titleCell(row.id, `${row.key} · ${row.name}`, row.description)}</td><td>${nameFor("users", row.owner_id)}</td><td>${row.member_ids?.length || 0}</td><td>${row.environment_ids?.length || 0} env / ${row.asset_ids?.length || 0} assets</td><td>${statusPill(row.status)}</td></tr>`;
  if (type === "assets") return `<tr><td>${titleCell(row.id, row.name, row.id)}</td><td>${escapeHtml(row.category)}</td><td>${nameFor("users", row.owner_id)}</td><td>${escapeHtml(row.location || "Unassigned")}</td><td>${statusPill(row.status)}</td><td>${tags(row.capabilities)}</td></tr>`;
  const ready = readiness(row);
  return `<tr><td>${titleCell(row.id, row.name, row.type)}</td><td>${projectName(row.project_id)}</td><td>${nameFor("users", row.owner_id)}</td><td>${row.member_ids?.length || 0} members / ${row.asset_ids?.length || 0} assets</td><td><span class="pill ${ready.level === "ok" ? "ok" : "warn"}">${ready.message}</span></td></tr>`;
}

function titleCell(id, title, subtitle) {
  return `<span class="row-title"><button data-open="${escapeHtml(id)}">${escapeHtml(title)}</button><small>${escapeHtml(subtitle || id)}</small></span>`;
}

function renderDetail(type, id) {
  const row = ({ identity: state.users, projects: state.projects, assets: state.assets, environments: state.environments }[type]).find((item) => item.id === id);
  if (!row) return;
  const detail = $("#detail-slot");
  detail.innerHTML = `
    <div class="detail-grid">
      <section class="detail-panel">
        <div class="tab-strip"><button class="active">Overview</button><button>Relationships</button><button>Activity</button></div>
        <h2>${escapeHtml(row.name || row.key || row.email)}</h2>
        <dl class="kv">${detailPairs(type, row).map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>
      </section>
      <aside class="detail-panel">
        <h3>Related records</h3>
        ${relationshipList(type, row)}
      </aside>
    </div>
  `;
  detail.scrollIntoView({ behavior: "smooth", block: "start" });
}

function detailPairs(type, row) {
  const common = [["ID", escapeHtml(row.id)], ["Status", statusPill(row.status || "active")], ["Updated", date(row.updated_at)]];
  if (type === "identity") return [["Email", escapeHtml(row.email)], ["Roles", roles(row.roles)], ...common];
  if (type === "projects") return [["Key", escapeHtml(row.key)], ["Owner", nameFor("users", row.owner_id)], ["Description", escapeHtml(row.description || "No description")], ["Members", String(row.member_ids?.length || 0)], ...common];
  if (type === "assets") return [["Category", escapeHtml(row.category)], ["Owner", nameFor("users", row.owner_id)], ["Location", escapeHtml(row.location || "Unassigned")], ["Capabilities", tags(row.capabilities)], ["Properties", escapeHtml(JSON.stringify(row.properties || {}))], ...common];
  const ready = readiness(row);
  return [["Type", escapeHtml(row.type)], ["Project", projectName(row.project_id)], ["Owner", nameFor("users", row.owner_id)], ["Readiness", `<span class="pill ${ready.level === "ok" ? "ok" : "warn"}">${ready.message}</span>`], ["Endpoints", String(row.endpoints?.length || 0)], ...common];
}

function relationshipList(type, row) {
  if (type === "projects") return listItems([...(row.environment_ids || []).map(projectEnvLabel), ...(row.asset_ids || []).map(assetLabel)]);
  if (type === "assets") return listItems([row.parent_id ? `Installed in ${assetLabel(row.parent_id)}` : "No parent asset", ...state.assets.filter((asset) => asset.parent_id === row.id).map((asset) => `Contains ${asset.name}`)]);
  if (type === "environments") return listItems([...(row.member_ids || []).map((id) => `Member ${nameFor("users", id)}`), ...(row.asset_ids || []).map((id) => `Asset ${assetLabel(id)}`), ...(row.endpoints || []).map((e) => `Endpoint ${e.name}: ${e.url}`)]);
  return listItems(state.projects.filter((project) => project.member_ids?.includes(row.id) || project.owner_id === row.id).map((project) => `Project ${project.key}`));
}

function openCreate(type) {
  const title = { identity: "Create user", projects: "Create project", assets: "Register asset", environments: "Create environment" }[type];
  $("#modal-title").textContent = title;
  $("#modal-body").innerHTML = formFor(type);
  modal.showModal();
  $("#modal-body form").addEventListener("submit", (event) => submitCreate(event, type));
}

function formFor(type) {
  const userOptions = state.users.map((u) => `<option value="${u.id}">${escapeHtml(u.name)}</option>`).join("");
  const projectOptions = state.projects.map((p) => `<option value="${p.id}">${escapeHtml(p.key)} · ${escapeHtml(p.name)}</option>`).join("");
  const assetOptions = `<option value="">No parent</option>${state.assets.map((a) => `<option value="${a.id}">${escapeHtml(a.name)}</option>`).join("")}`;
  if (type === "identity") return `<form class="form-grid"><label>Name<input name="name" required /></label><label>Email<input name="email" type="email" required /></label><label>Role<select name="role"><option>Admin</option><option>Operator</option><option>Viewer</option></select></label><label>Scope<select name="scope"><option>platform</option><option>project</option></select></label><button class="primary-button full" type="submit">Create user</button></form>`;
  if (type === "projects") return `<form class="form-grid"><label>Key<input name="key" required /></label><label>Name<input name="name" required /></label><label>Owner<select name="owner_id" required>${userOptions}</select></label><label class="full">Description<textarea name="description"></textarea></label><button class="primary-button full" type="submit">Create project</button></form>`;
  if (type === "assets") return `<form class="form-grid"><label>Name<input name="name" required /></label><label>Category<select name="category"><option>server</option><option>workstation</option><option>vm</option><option>gpu</option><option>memory</option></select></label><label>Status<select name="status"><option>available</option><option>in_use</option><option>maintenance</option><option>retired</option></select></label><label>Owner<select name="owner_id">${userOptions}</select></label><label>Parent asset<select name="parent_id">${assetOptions}</select></label><label>Location<input name="location" /></label><label class="full">Capabilities<input name="capabilities" placeholder="cuda, linux, test-runner" /></label><button class="primary-button full" type="submit">Register asset</button></form>`;
  return `<form class="form-grid"><label>Name<input name="name" required /></label><label>Type<select name="type"><option>DEV</option><option>QA</option><option>QE</option></select></label><label>Project<select name="project_id" required>${projectOptions}</select></label><label>Owner<select name="owner_id" required>${userOptions}</select></label><label class="full">Endpoint URL<input name="endpoint" placeholder="https://qa.example.local" /></label><button class="primary-button full" type="submit">Create environment</button></form>`;
}

async function submitCreate(event, type) {
  event.preventDefault();
  const form = new FormData(event.target);
  const payload = Object.fromEntries(form.entries());
  if (type === "identity") {
    payload.roles = [{ scope: payload.scope, name: payload.role }];
    delete payload.scope;
    delete payload.role;
  }
  if (type === "assets") {
    payload.capabilities = String(payload.capabilities || "").split(",").map((item) => item.trim()).filter(Boolean);
    payload.properties = {};
  }
  if (type === "environments") {
    payload.member_ids = [payload.owner_id];
    payload.asset_ids = [];
    payload.endpoints = payload.endpoint ? [{ name: "primary", url: payload.endpoint }] : [];
    delete payload.endpoint;
  }
  try {
    if (!state.apiOnline) throw new Error("mock_mode");
    await apiPost({ identity: "/v1/users", projects: "/v1/projects", assets: "/v1/assets", environments: "/v1/environments" }[type], payload);
    modal.close();
    await loadData();
    toast(`${resourceConfig(type).title} saved.`);
  } catch (error) {
    addMock(type, payload);
    modal.close();
    render();
    toast(state.apiOnline ? `Saved locally after API error: ${error.message}` : "Saved to local mock state.");
  }
}

function addMock(type, payload) {
  const idPrefix = { identity: "usr", projects: "prj", assets: "ast", environments: "env" }[type];
  const collection = { identity: "users", projects: "projects", assets: "assets", environments: "environments" }[type];
  const item = { ...payload, id: `${idPrefix}_local_${Date.now()}`, status: payload.status || "active", created_at: new Date().toISOString(), updated_at: new Date().toISOString() };
  if (type === "projects") {
    item.member_ids = [item.owner_id];
    item.asset_ids = [];
    item.environment_ids = [];
  }
  if (type === "identity") item.status = "active";
  state[collection].push(item);
  state.auditEvents.unshift({ id: `aud_local_${Date.now()}`, actor_id: ACTOR_ID, action: `${collection}.created`, resource_type: collection, resource_id: item.id, occurred_at: new Date().toISOString(), metadata: {} });
}

function bindToolbar(type) {
  content.querySelectorAll("[data-filter]").forEach((control) => {
    control.addEventListener("input", () => {
      state.filters[control.dataset.filter] = control.value;
      renderResource(type);
    });
  });
  content.querySelector("[data-clear]").addEventListener("click", () => {
    state.filters = {};
    renderResource(type);
  });
}

function filterControl(filter) {
  return `<label>${filter.label}<select data-filter="${filter.key}">${filter.values.map((value) => `<option value="${value}" ${state.filters[filter.key] === value ? "selected" : ""}>${value}</option>`).join("")}</select></label>`;
}

function metric(label, value, help) {
  return `<div class="metric"><span>${label}</span><strong>${value}</strong><small>${help}</small></div>`;
}

function setupCard(label, complete, help) {
  return `<section class="panel"><h3>${label} <span class="pill ${complete ? "ok" : "warn"}">${complete ? "Ready" : "Needs work"}</span></h3><p class="muted">${help}</p></section>`;
}

function activityList(events) {
  if (!events.length) return `<div class="empty-state">No audit events yet.</div>`;
  return `<ul class="activity-list">${events.map((event) => `<li><strong>${escapeHtml(event.action)}</strong><br><span class="muted">${escapeHtml(event.resource_type)} · ${escapeHtml(event.resource_id)} · ${date(event.occurred_at)}</span></li>`).join("")}</ul>`;
}

function readiness(env) {
  const issues = [];
  if (!env.owner_id) issues.push("missing owner");
  if (!env.asset_ids?.length) issues.push("missing assets");
  if (!env.endpoints?.length) issues.push("missing endpoint");
  if ((env.asset_ids || []).some((id) => state.assets.find((asset) => asset.id === id)?.status === "retired")) issues.push("inactive asset");
  return issues.length ? { level: "warn", message: issues.join(", ") } : { level: "ok", message: "ready" };
}

function statusPill(status = "active") {
  const tone = ["active", "available", "in_use"].includes(status) ? "ok" : ["inactive", "maintenance", "archived"].includes(status) ? "warn" : "bad";
  return `<span class="pill ${tone}">${escapeHtml(status)}</span>`;
}

function roles(value = []) {
  return value.length ? value.map((role) => `<span class="role-pill">${escapeHtml(role.scope)}:${escapeHtml(role.name)}</span>`).join(" ") : `<span class="muted">No roles</span>`;
}

function tags(value = []) {
  return value.length ? value.map((tag) => `<span class="pill">${escapeHtml(tag)}</span>`).join(" ") : `<span class="muted">None</span>`;
}

function nameFor(collection, id) {
  return escapeHtml((state[collection] || []).find((item) => item.id === id)?.name || id || "Unassigned");
}

function projectName(id) {
  const project = state.projects.find((item) => item.id === id);
  return escapeHtml(project ? `${project.key} · ${project.name}` : id || "Unassigned");
}

function assetLabel(id) {
  return escapeHtml(state.assets.find((item) => item.id === id)?.name || id);
}

function projectEnvLabel(id) {
  return `Environment ${escapeHtml(state.environments.find((item) => item.id === id)?.name || id)}`;
}

function listItems(items) {
  return items.length ? `<ul class="link-list">${items.map((item) => `<li>${item}</li>`).join("")}</ul>` : `<div class="empty-state">No related records.</div>`;
}

function activeCount(items) {
  return items.filter((item) => item.status === "active").length;
}

function linkedProjects() {
  return state.projects.filter((project) => project.asset_ids?.length || project.environment_ids?.length).length;
}

function countFor(key) {
  return { dashboard: "", identity: state.users.length, projects: state.projects.length, assets: state.assets.length, environments: state.environments.length }[key] || "";
}

function date(value) {
  if (!value) return "Not recorded";
  return new Intl.DateTimeFormat("en", { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.add("show");
  setTimeout(() => node.classList.remove("show"), 2800);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}
