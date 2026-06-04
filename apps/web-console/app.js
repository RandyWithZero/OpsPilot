const API_BASE = localStorage.getItem("opspilot_api_base") || "http://localhost:8080";
const ACTOR_ID = "web-console";
const navItems = [
  ["dashboard", "Dashboard"],
  ["identity", "Identity"],
  ["projects", "Projects"],
  ["assets", "Assets"],
  ["environments", "Environments"],
];

const collections = {
  identity: "users",
  projects: "projects",
  assets: "assets",
  environments: "environments",
};

const endpoints = {
  identity: "/v1/users",
  projects: "/v1/projects",
  assets: "/v1/assets",
  environments: "/v1/environments",
};

const state = {
  route: "dashboard",
  query: "",
  filters: {},
  detail: null,
  apiOnline: false,
  user: sessionStorage.getItem("opspilot_user") || "",
  role: sessionStorage.getItem("opspilot_role") || "Admin",
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
  state.role = roleFromEmail(state.user);
  sessionStorage.setItem("opspilot_user", state.user);
  sessionStorage.setItem("opspilot_role", state.role);
  showApp();
}

function signOut() {
  sessionStorage.removeItem("opspilot_user");
  sessionStorage.removeItem("opspilot_role");
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
    state.users = users;
    state.projects = projects;
    state.assets = assets;
    state.environments = environments;
    state.auditEvents = auditEvents;
    if (forceToast) toast("Foundation API data refreshed.");
  } catch (error) {
    state.apiOnline = false;
    state.users = clone(seed.users);
    state.projects = clone(seed.projects);
    state.assets = clone(seed.assets);
    state.environments = clone(seed.environments);
    state.auditEvents = clone(seed.auditEvents);
    if (forceToast) toast("Using local mock inventory because the API is unavailable.");
  }
  render();
}

async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) throw new Error(path);
  return response.json();
}

async function apiRequest(method, path, payload) {
  const options = {
    method,
    headers: { "Content-Type": "application/json", "X-Actor-ID": ACTOR_ID },
  };
  if (payload !== undefined) options.body = JSON.stringify(payload);
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    const data = await response.json().catch(() => ({ error: "request_failed" }));
    throw new Error(data.error || "request_failed");
  }
  return response.json();
}

function renderNav() {
  $("#nav").innerHTML = navItems.map(([key, label]) => `<button data-route="${key}"><span>${label}</span><small>${countFor(key)}</small></button>`).join("");
  $("#nav").onclick = (event) => {
    const button = event.target.closest("button[data-route]");
    if (!button) return;
    state.route = button.dataset.route;
    state.filters = {};
    state.detail = null;
    render();
  };
}

function render() {
  $("#api-state").innerHTML = `${state.apiOnline ? "Foundation API live" : "Local mock mode"} <span class="role-badge">${state.role}</span>`;
  $(".status-dot").classList.toggle("live", state.apiOnline);
  $("#project-switcher").innerHTML = `<option>All projects</option>${state.projects.map((p) => `<option>${escapeHtml(p.key)} · ${escapeHtml(p.name)}</option>`).join("")}`;
  renderNav();
  document.querySelectorAll("#nav button").forEach((button) => button.classList.toggle("active", button.dataset.route === state.route));
  if (state.route === "dashboard") renderDashboard();
  if (state.route === "identity") renderResource("identity");
  if (state.route === "projects") renderResource("projects");
  if (state.route === "assets") renderResource("assets");
  if (state.route === "environments") renderResource("environments");
}

function renderDashboard() {
  const readinessIssues = state.environments.filter((env) => readiness(env).level !== "ok");
  const isEmpty = !state.users.length && !state.projects.length && !state.assets.length && !state.environments.length;
  content.innerHTML = `
    <div class="page-head">
      <div>
        <p class="eyebrow">Authenticated shell</p>
        <h1>Inventory command center</h1>
        <p class="muted">Dense setup status for identity, projects, assets, and environment readiness.</p>
      </div>
    ${actionButton("create", "Create project", "primary-button", "create-project", { type: "projects" })}
    </div>
    ${permissionBanner()}
    ${isEmpty && state.apiOnline ? `<section class="empty-state panel"><strong>Live inventory is empty.</strong><span>Create the first user, then project, asset, and environment records. No mock data is being displayed while the API is reachable.</span></section>` : ""}
    <div class="metric-grid">
      ${metric("Users", state.users.length, `${activeCount(state.users)} active identities`)}
      ${metric("Projects", state.projects.length, `${linkedProjects()} with inventory links`)}
      ${metric("Assets", state.assets.length, `${state.assets.filter((a) => a.parent_id).length} installed components`)}
      ${metric("Environments", state.environments.length, `${readinessIssues.length} readiness warnings`)}
    </div>
    <div class="setup-grid">
      ${setupCard("Identity", state.users.length > 0, state.users.length ? "Users and platform roles are available." : "Create the first admin identity.")}
      ${setupCard("Projects", state.projects.length > 0 && state.projects.every((p) => p.owner_id), state.projects.length ? "Project owners and member references are recorded." : "Create a project after identity setup.")}
      ${setupCard("Assets", state.assets.some((a) => a.capabilities?.length), state.assets.length ? "Capability-tagged inventory exists for allocation." : "Register physical or virtual assets.")}
      ${setupCard("Environments", state.environments.length > 0 && readinessIssues.length === 0, state.environments.length ? readinessIssues.length ? "Some environments need owners, assets, or endpoints." : "All environments are ready." : "Create DEV, QA, or QE environments.")}
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
  bindActions(content);
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
      ${actionButton("create", config.action, "primary-button", `create-${type}`, { type })}
    </div>
    ${permissionBanner()}
    <div class="toolbar">
      <label>Search this view<input data-filter="localQuery" type="search" value="${escapeHtml(state.filters.localQuery || "")}" placeholder="${config.search}" /></label>
      ${config.filters.map((filter) => filterControl(filter)).join("")}
      <label>Rows<select data-filter="limit"><option>10</option><option ${state.filters.limit === "25" ? "selected" : ""}>25</option></select></label>
      <button class="ghost-button" data-clear>Clear</button>
    </div>
    <section class="table-wrap" aria-label="${config.title} table">
      ${rows.length ? tableFor(type, rows) : emptyStateFor(type)}
    </section>
    <section id="detail-slot">${state.detail?.type === type ? detailMarkup(type, state.detail.id) : ""}</section>
  `;
  bindToolbar(type);
  bindActions(content);
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
    identity: ["User", "Status", "Roles", "Updated", "Actions"],
    projects: ["Project", "Owner", "Members", "Links", "Status", "Actions"],
    assets: ["Asset", "Category", "Owner", "Location", "Status", "Actions"],
    environments: ["Environment", "Project", "Owner", "Bindings", "Readiness", "Actions"],
  }[type];
  return `<table><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => rowFor(type, row)).join("")}</tbody></table>`;
}

function rowFor(type, row) {
  if (type === "identity") return `<tr><td>${titleCell(row.id, row.name, row.email)}</td><td>${statusPill(row.status)}</td><td>${roles(row.roles)}</td><td>${date(row.updated_at)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "projects") return `<tr><td>${titleCell(row.id, `${row.key} · ${row.name}`, row.description)}</td><td>${nameFor("users", row.owner_id)}</td><td>${row.member_ids?.length || 0}</td><td>${row.environment_ids?.length || 0} env / ${row.asset_ids?.length || 0} assets</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "assets") return `<tr><td>${titleCell(row.id, row.name, row.id)}</td><td>${escapeHtml(row.category)}</td><td>${nameFor("users", row.owner_id)}</td><td>${escapeHtml(row.location || "Unassigned")}</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
  const ready = readiness(row);
  return `<tr><td>${titleCell(row.id, row.name, row.type)}</td><td>${projectName(row.project_id)}</td><td>${nameFor("users", row.owner_id)}</td><td>${row.member_ids?.length || 0} members / ${row.asset_ids?.length || 0} assets</td><td><span class="pill ${ready.level === "ok" ? "ok" : "warn"}">${ready.message}</span></td><td>${rowActions(type, row)}</td></tr>`;
}

function rowActions(type, row) {
  const statusLabel = statusActionLabel(type, row);
  return `<div class="action-row">
    ${actionButton("edit", "Edit", "ghost-button small", `edit-${type}-${row.id}`, { type, id: row.id })}
    ${statusLabel ? actionButton("status", statusLabel, "ghost-button small", `status-${type}-${row.id}`, { type, id: row.id }) : ""}
    ${actionButton("delete", "Delete", "ghost-button small danger", `delete-${type}-${row.id}`, { type, id: row.id })}
  </div>`;
}

function titleCell(id, title, subtitle) {
  return `<span class="row-title"><button data-action="open" data-id="${escapeHtml(id)}">${escapeHtml(title)}</button><small>${escapeHtml(subtitle || id)}</small></span>`;
}

function detailMarkup(type, id) {
  const row = collectionFor(type).find((item) => item.id === id);
  if (!row) return "";
  return `
    <div class="detail-grid">
      <section class="detail-panel">
        <div class="tab-strip"><button class="active">Overview</button><button>Relationships</button><button>Activity</button></div>
        <div class="detail-heading">
          <h2>${escapeHtml(row.name || row.key || row.email)}</h2>
          <div class="action-row">${rowActions(type, row)}</div>
        </div>
        <dl class="kv">${detailPairs(type, row).map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>
      </section>
      <aside class="detail-panel">
        <h3>Relationship controls</h3>
        ${relationshipControls(type, row)}
      </aside>
    </div>
  `;
}

function detailPairs(type, row) {
  const common = [["ID", escapeHtml(row.id)], ["Status", statusPill(row.status || "active")], ["Updated", date(row.updated_at)]];
  if (type === "identity") return [["Email", escapeHtml(row.email)], ["Roles", roles(row.roles)], ...common];
  if (type === "projects") return [["Key", escapeHtml(row.key)], ["Owner", nameFor("users", row.owner_id)], ["Description", escapeHtml(row.description || "No description")], ["Members", String(row.member_ids?.length || 0)], ...common];
  if (type === "assets") return [["Category", escapeHtml(row.category)], ["Owner", nameFor("users", row.owner_id)], ["Location", escapeHtml(row.location || "Unassigned")], ["Capabilities", tags(row.capabilities)], ["Properties", escapeHtml(JSON.stringify(row.properties || {}))], ...common];
  const ready = readiness(row);
  return [["Type", escapeHtml(row.type)], ["Project", projectName(row.project_id)], ["Owner", nameFor("users", row.owner_id)], ["Readiness", `<span class="pill ${ready.level === "ok" ? "ok" : "warn"}">${ready.message}</span>`], ["Endpoints", String(row.endpoints?.length || 0)], ...common];
}

function relationshipControls(type, row) {
  if (state.role === "Viewer") return `<div class="permission-denied"><strong>Permission denied</strong><span>Viewer can inspect relationships but cannot change bindings.</span></div>${relationshipList(type, row)}`;
  if (type === "projects") {
    const availableAssets = state.assets.filter((asset) => !(row.asset_ids || []).includes(asset.id));
    const availableEnvironments = state.environments.filter((env) => env.project_id === row.id && !(row.environment_ids || []).includes(env.id));
    return `
      <form class="inline-form" data-action="link-project-asset" data-id="${row.id}">
        <label>Link asset<select name="asset_id">${options(availableAssets, "No unlinked assets")}</select></label>
        <button class="ghost-button small" type="submit">Link</button>
      </form>
      <form class="inline-form" data-action="link-project-environment" data-id="${row.id}">
        <label>Link environment<select name="environment_id">${options(availableEnvironments, "No unlinked environments")}</select></label>
        <button class="ghost-button small" type="submit">Link</button>
      </form>
      <h4>Linked assets</h4>${linkedList(row.asset_ids || [], "assets", "unlink-project-asset", row.id)}
      <h4>Linked environments</h4>${linkedList(row.environment_ids || [], "environments", "unlink-project-environment", row.id)}
    `;
  }
  if (type === "environments") {
    const availableAssets = state.assets.filter((asset) => !(row.asset_ids || []).includes(asset.id));
    const availableMembers = state.users.filter((user) => !(row.member_ids || []).includes(user.id));
    return `
      <form class="inline-form" data-action="bind-environment-asset" data-id="${row.id}">
        <label>Bind asset<select name="asset_id">${options(availableAssets, "No unbound assets")}</select></label>
        <button class="ghost-button small" type="submit">Bind</button>
      </form>
      <form class="inline-form" data-action="bind-environment-member" data-id="${row.id}">
        <label>Bind member<select name="member_id">${options(availableMembers, "No unbound members")}</select></label>
        <button class="ghost-button small" type="submit">Bind</button>
      </form>
      <h4>Assets</h4>${linkedList(row.asset_ids || [], "assets", "unbind-environment-asset", row.id)}
      <h4>Members</h4>${linkedList(row.member_ids || [], "users", "unbind-environment-member", row.id)}
      <h4>Endpoints</h4>${listItems((row.endpoints || []).map((endpoint) => `Endpoint ${escapeHtml(endpoint.name)}: ${escapeHtml(endpoint.url)}`))}
    `;
  }
  return relationshipList(type, row);
}

function relationshipList(type, row) {
  if (type === "projects") return listItems([...(row.environment_ids || []).map(projectEnvLabel), ...(row.asset_ids || []).map(assetLabel)]);
  if (type === "assets") return listItems([row.parent_id ? `Installed in ${assetLabel(row.parent_id)}` : "No parent asset", ...state.assets.filter((asset) => asset.parent_id === row.id).map((asset) => `Contains ${escapeHtml(asset.name)}`)]);
  if (type === "environments") return listItems([...(row.member_ids || []).map((id) => `Member ${nameFor("users", id)}`), ...(row.asset_ids || []).map((id) => `Asset ${assetLabel(id)}`), ...(row.endpoints || []).map((e) => `Endpoint ${escapeHtml(e.name)}: ${escapeHtml(e.url)}`)]);
  return listItems(state.projects.filter((project) => project.member_ids?.includes(row.id) || project.owner_id === row.id).map((project) => `Project ${escapeHtml(project.key)}`));
}

function linkedList(ids, source, action, ownerId) {
  if (!ids.length) return `<div class="empty-state compact">No linked records.</div>`;
  return `<ul class="link-list">${ids.map((id) => `<li><span>${labelFor(source, id)}</span>${actionButton("link", "Unlink", "ghost-button small", `${action}-${id}`, { actionName: action, id: ownerId, targetId: id })}</li>`).join("")}</ul>`;
}

function openCreate(type) {
  if (!can("create")) return deny("create records");
  openFormModal({ mode: "create", type });
}

function openEdit(type, id) {
  if (!can("edit")) return deny("edit records");
  const row = collectionFor(type).find((item) => item.id === id);
  if (row) openFormModal({ mode: "edit", type, row });
}

function openFormModal({ mode, type, row = {} }) {
  const config = resourceConfig(type);
  $("#modal-title").textContent = mode === "create" ? config.action : `Edit ${config.title}`;
  $("#modal-body").innerHTML = formFor(type, row, mode);
  modal.showModal();
  $("#modal-body form").addEventListener("submit", (event) => submitForm(event, type, row.id));
}

function formFor(type, row, mode) {
  const userOptions = state.users.map((u) => `<option value="${u.id}" ${row.owner_id === u.id ? "selected" : ""}>${escapeHtml(u.name)}</option>`).join("");
  const projectOptions = state.projects.map((p) => `<option value="${p.id}" ${row.project_id === p.id ? "selected" : ""}>${escapeHtml(p.key)} · ${escapeHtml(p.name)}</option>`).join("");
  const assetOptions = `<option value="">No parent</option>${state.assets.filter((asset) => asset.id !== row.id).map((a) => `<option value="${a.id}" ${row.parent_id === a.id ? "selected" : ""}>${escapeHtml(a.name)}</option>`).join("")}`;
  const submit = mode === "create" ? resourceConfig(type).action : "Save changes";
  if (type === "identity") return `<form class="form-grid"><label>Name<input name="name" value="${escapeAttr(row.name)}" required /></label><label>Email<input name="email" type="email" value="${escapeAttr(row.email)}" required /></label><label>Role<select name="role">${selectedOptions(["Admin", "Operator", "Viewer"], row.roles?.[0]?.name || "Admin")}</select></label><label>Scope<select name="scope">${selectedOptions(["platform", "project"], row.roles?.[0]?.scope || "platform")}</select></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "projects") return `<form class="form-grid"><label>Key<input name="key" value="${escapeAttr(row.key)}" required /></label><label>Name<input name="name" value="${escapeAttr(row.name)}" required /></label><label>Owner<select name="owner_id" required>${userOptions}</select></label><label>Status<select name="status">${selectedOptions(["active", "archived"], row.status || "active")}</select></label><label class="full">Description<textarea name="description">${escapeHtml(row.description || "")}</textarea></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "assets") return `<form class="form-grid"><label>Name<input name="name" value="${escapeAttr(row.name)}" required /></label><label>Category<select name="category">${selectedOptions(["server", "workstation", "vm", "gpu", "memory"], row.category || "server")}</select></label><label>Status<select name="status">${selectedOptions(["available", "in_use", "maintenance", "retired"], row.status || "available")}</select></label><label>Owner<select name="owner_id"><option value="">Unassigned</option>${userOptions}</select></label><label>Parent asset<select name="parent_id">${assetOptions}</select></label><label>Location<input name="location" value="${escapeAttr(row.location)}" /></label><label class="full">Capabilities<input name="capabilities" value="${escapeAttr((row.capabilities || []).join(", "))}" placeholder="cuda, linux, test-runner" /></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  return `<form class="form-grid"><label>Name<input name="name" value="${escapeAttr(row.name)}" required /></label><label>Type<select name="type">${selectedOptions(["DEV", "QA", "QE"], row.type || "DEV")}</select></label><label>Project<select name="project_id" required>${projectOptions}</select></label><label>Owner<select name="owner_id" required>${userOptions}</select></label><label>Status<select name="status">${selectedOptions(["active", "inactive"], row.status || "active")}</select></label><label class="full">Endpoint URL<input name="endpoint" value="${escapeAttr(row.endpoints?.[0]?.url)}" placeholder="https://qa.example.local" /></label><button class="primary-button full" type="submit">${submit}</button></form>`;
}

async function submitForm(event, type, id) {
  event.preventDefault();
  const payload = payloadFromForm(new FormData(event.target), type);
  try {
    if (id) await mutate("PATCH", `${endpoints[type]}/${id}`, payload, type, id, (item) => ({ ...item, ...payload, updated_at: new Date().toISOString() }));
    else await mutate("POST", endpoints[type], payload, type, null, () => addLocal(type, payload));
    modal.close();
    await afterMutation(type, id);
    toast(`${resourceConfig(type).title} saved.`);
  } catch (error) {
    showError(error.message);
  }
}

function payloadFromForm(form, type) {
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
    payload.member_ids = [];
    payload.asset_ids = [];
    payload.endpoints = payload.endpoint ? [{ name: "primary", url: payload.endpoint }] : [];
    delete payload.endpoint;
  }
  return payload;
}

async function handleStatus(type, id) {
  if (!can("delete")) return deny("change lifecycle state");
  const item = collectionFor(type).find((row) => row.id === id);
  if (!item) return;
  const nextStatus = nextStatusFor(type, item);
  await mutate("PATCH", `${endpoints[type]}/${id}`, { status: nextStatus }, type, id, (row) => ({ ...row, status: nextStatus, updated_at: new Date().toISOString() }));
  await afterMutation(type, id);
  toast(`${resourceConfig(type).title} marked ${nextStatus}.`);
}

async function handleDelete(type, id) {
  if (!can("delete")) return deny("delete records");
  const item = collectionFor(type).find((row) => row.id === id);
  if (!item || !confirm(`Delete ${item.name || item.key || item.email}? This action is reversible only through a new create flow.`)) return;
  await mutate("DELETE", `${endpoints[type]}/${id}`, undefined, type, id, () => null);
  state.detail = null;
  await afterMutation(type);
  toast(`${resourceConfig(type).title} deleted.`);
}

async function handleRelationship(actionName, id, targetId, form) {
  if (!can("link")) return deny("change bindings");
  const value = targetId || new FormData(form).get(actionValueKey(actionName));
  if (!value) return showError("Choose a record before saving the binding.");
  if (actionName === "link-project-asset") await mutate("POST", `/v1/projects/${id}/assets/${value}`, undefined, "projects", id, (project) => ({ ...project, asset_ids: unique([...(project.asset_ids || []), value]) }));
  if (actionName === "unlink-project-asset") await mutate("DELETE", `/v1/projects/${id}/assets/${value}`, undefined, "projects", id, (project) => ({ ...project, asset_ids: (project.asset_ids || []).filter((assetId) => assetId !== value) }));
  if (actionName === "link-project-environment") await mutate("POST", `/v1/projects/${id}/environments/${value}`, undefined, "projects", id, (project) => ({ ...project, environment_ids: unique([...(project.environment_ids || []), value]) }));
  if (actionName === "unlink-project-environment") await mutate("DELETE", `/v1/projects/${id}/environments/${value}`, undefined, "projects", id, (project) => ({ ...project, environment_ids: (project.environment_ids || []).filter((envId) => envId !== value) }));
  if (actionName === "bind-environment-asset") await patchEnvironment(id, (env) => ({ asset_ids: unique([...(env.asset_ids || []), value]) }));
  if (actionName === "unbind-environment-asset") await patchEnvironment(id, (env) => ({ asset_ids: (env.asset_ids || []).filter((assetId) => assetId !== value) }));
  if (actionName === "bind-environment-member") await patchEnvironment(id, (env) => ({ member_ids: unique([...(env.member_ids || []), value]) }));
  if (actionName === "unbind-environment-member") await patchEnvironment(id, (env) => ({ member_ids: (env.member_ids || []).filter((memberId) => memberId !== value) }));
  await afterMutation(state.route, id);
  toast("Binding updated.");
}

async function patchEnvironment(id, changeFn) {
  const env = state.environments.find((item) => item.id === id);
  const patch = changeFn(env);
  await mutate("PATCH", `/v1/environments/${id}`, patch, "environments", id, (item) => ({ ...item, ...patch, updated_at: new Date().toISOString() }));
}

async function mutate(method, path, payload, type, id, localChange) {
  if (state.apiOnline) {
    await apiRequest(method, path, payload);
    return;
  }
  applyLocal(type, id, localChange);
}

async function afterMutation(type, id = null) {
  if (id) state.detail = { type, id };
  if (state.apiOnline) await loadData();
  else render();
}

function applyLocal(type, id, localChange) {
  const collection = collections[type];
  if (!id) {
    state[collection].push(localChange());
    addAudit(`${collection}.created`, collection, state[collection].at(-1).id);
    return;
  }
  const index = state[collection].findIndex((item) => item.id === id);
  if (index < 0) return;
  const updated = localChange(state[collection][index]);
  if (updated === null) state[collection].splice(index, 1);
  else state[collection][index] = updated;
  addAudit(`${collection}.updated`, collection, id);
}

function addLocal(type, payload) {
  const idPrefix = { identity: "usr", projects: "prj", assets: "ast", environments: "env" }[type];
  const item = { ...payload, id: `${idPrefix}_local_${Date.now()}`, status: payload.status || "active", created_at: new Date().toISOString(), updated_at: new Date().toISOString() };
  if (type === "projects") {
    item.member_ids = [item.owner_id].filter(Boolean);
    item.asset_ids = [];
    item.environment_ids = [];
  }
  if (type === "identity") item.status = "active";
  if (type === "environments") {
    item.member_ids = [item.owner_id].filter(Boolean);
    item.asset_ids = [];
  }
  return item;
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

function bindActions(root) {
  root.querySelectorAll("[data-action]").forEach((node) => {
    if (node.tagName === "FORM") {
      node.addEventListener("submit", async (event) => {
        event.preventDefault();
        await handleRelationship(node.dataset.action, node.dataset.id, "", node).catch((error) => showError(error.message));
      });
      return;
    }
    node.addEventListener("click", async () => {
      const action = node.dataset.action;
      const type = node.dataset.type || state.route;
      const id = node.dataset.id;
      try {
        if (action === "open") {
          state.detail = { type, id };
          renderResource(type);
        } else if (action === "create" || action?.startsWith("create-")) {
          openCreate(node.dataset.type || (action === "create-project" ? "projects" : action.replace("create-", "")));
        } else if (action === "edit") {
          openEdit(type, id);
        } else if (action === "status") {
          await handleStatus(type, id);
        } else if (action === "delete") {
          await handleDelete(type, id);
        } else if (action === "link") {
          await handleRelationship(node.dataset.actionName, id, node.dataset.targetId, null);
        }
      } catch (error) {
        showError(error.message);
      }
    });
  });
}

function filterControl(filter) {
  return `<label>${filter.label}<select data-filter="${filter.key}">${filter.values.map((value) => `<option value="${value}" ${state.filters[filter.key] === value ? "selected" : ""}>${value}</option>`).join("")}</select></label>`;
}

function actionButton(permission, label, className, id, dataset = {}) {
  const allowed = can(permission);
  const attrs = Object.entries(dataset).map(([key, value]) => `data-${kebab(key)}="${escapeAttr(value)}"`).join(" ");
  return `<button class="${className}" data-action="${permission}" ${attrs} ${allowed ? "" : "disabled aria-disabled=\"true\" title=\"Permission denied\""}>${label}</button>`;
}

function permissionBanner() {
  return state.role === "Viewer" ? `<section class="permission-denied"><strong>Permission denied for write actions.</strong><span>Viewer role can inspect dashboard, inventory, relationships, and audit context, but create/edit/link/archive/delete controls are disabled.</span></section>` : "";
}

function deny(action) {
  toast(`Permission denied: ${state.role} cannot ${action}.`);
}

function can(permission) {
  if (permission === "open") return true;
  if (state.role === "Admin") return true;
  if (state.role === "Operator") return ["create", "edit", "link"].includes(permission);
  return false;
}

function emptyStateFor(type) {
  const config = resourceConfig(type);
  const mode = state.apiOnline ? "Live API returned no records." : "Local mock inventory has no matching records.";
  return `<div class="empty-state"><strong>No ${config.title.toLowerCase()} found.</strong><span>${mode}</span></div>`;
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

function options(items, emptyLabel) {
  return items.length ? items.map((item) => `<option value="${item.id}">${labelFor(collectionNameForItem(item), item.id, false)}</option>`).join("") : `<option value="">${emptyLabel}</option>`;
}

function selectedOptions(values, selected) {
  return values.map((value) => `<option ${value === selected ? "selected" : ""}>${value}</option>`).join("");
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

function labelFor(source, id, safe = true) {
  const maps = {
    users: state.users,
    assets: state.assets,
    environments: state.environments,
    projects: state.projects,
  };
  const item = maps[source]?.find((row) => row.id === id);
  const label = item?.key ? `${item.key} · ${item.name}` : item?.name || item?.email || id;
  return safe ? escapeHtml(label) : label;
}

function collectionNameForItem(item) {
  if ("email" in item) return "users";
  if ("category" in item) return "assets";
  if ("type" in item && "project_id" in item) return "environments";
  return "projects";
}

function listItems(items) {
  return items.length ? `<ul class="link-list">${items.map((item) => `<li>${item}</li>`).join("")}</ul>` : `<div class="empty-state compact">No related records.</div>`;
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

function collectionFor(type) {
  return state[collections[type]];
}

function roleFromEmail(email) {
  const value = email.toLowerCase();
  if (value.includes("viewer")) return "Viewer";
  if (value.includes("operator")) return "Operator";
  return "Admin";
}

function statusActionLabel(type, row) {
  if (type === "identity") return row.status === "inactive" ? "Reactivate" : "Deactivate";
  if (type === "projects") return row.status === "archived" ? "Restore" : "Archive";
  if (type === "assets") return row.status === "retired" ? "Restore" : "Retire";
  if (type === "environments") return row.status === "inactive" ? "Activate" : "Deactivate";
  return "";
}

function nextStatusFor(type, row) {
  if (type === "identity") return row.status === "inactive" ? "active" : "inactive";
  if (type === "projects") return row.status === "archived" ? "active" : "archived";
  if (type === "assets") return row.status === "retired" ? "available" : "retired";
  if (type === "environments") return row.status === "inactive" ? "active" : "inactive";
  return row.status || "active";
}

function actionValueKey(actionName) {
  if (actionName.includes("asset")) return "asset_id";
  if (actionName.includes("environment")) return "environment_id";
  return "member_id";
}

function addAudit(action, resourceType, resourceId) {
  state.auditEvents.unshift({ id: `aud_local_${Date.now()}`, actor_id: ACTOR_ID, action, resource_type: resourceType, resource_id: resourceId, occurred_at: new Date().toISOString(), metadata: {} });
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function date(value) {
  if (!value) return "Not recorded";
  return new Intl.DateTimeFormat("en", { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.add("show");
  setTimeout(() => node.classList.remove("show"), 3200);
}

function showError(message) {
  toast(`Error: ${message}`);
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function kebab(value) {
  return value.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}

function escapeAttr(value) {
  return escapeHtml(value);
}
