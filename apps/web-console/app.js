const API_BASE = localStorage.getItem("opspilot_api_base") || "http://localhost:8080";
const ACTOR_ID = "web-console";
const navItems = [
  ["dashboard", "工作台"],
  ["bigscreen", "Dashboard 大屏"],
  ["tasks", "运维任务"],
  ["projects", "项目管理"],
  ["assets", "资产管理"],
  ["environments", "环境管理"],
  ["identity", "用户权限"],
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
    { id: "usr_mock_admin", name: "王少琪", email: "admin@opspilot.cn", status: "active", roles: [{ scope: "platform", name: "Admin" }], updated_at: "2026-06-04T07:18:00Z" },
    { id: "usr_mock_ops", name: "李伟", email: "operator@opspilot.cn", status: "active", roles: [{ scope: "project", name: "Operator" }], updated_at: "2026-06-04T07:19:00Z" },
    { id: "usr_mock_view", name: "陈敏", email: "viewer@opspilot.cn", status: "inactive", roles: [{ scope: "project", name: "Viewer" }], updated_at: "2026-06-04T07:20:00Z" },
  ],
  projects: [
    { id: "prj_mock_core", key: "OPS", name: "智能运营中台", description: "统一纳管项目、资产、环境与智能流程。", owner_id: "usr_mock_admin", member_ids: ["usr_mock_admin", "usr_mock_ops"], asset_ids: ["ast_mock_ws", "ast_mock_gpu"], environment_ids: ["env_mock_dev", "env_mock_qa"], status: "active", updated_at: "2026-06-04T07:21:00Z" },
    { id: "prj_mock_lab", key: "LAB", name: "自动化测试平台", description: "QA/QE 自动化执行与质量报告归档。", owner_id: "usr_mock_ops", member_ids: ["usr_mock_ops"], asset_ids: ["ast_mock_vm"], environment_ids: ["env_mock_qe"], status: "active", updated_at: "2026-06-04T07:22:00Z" },
  ],
  assets: [
    { id: "ast_mock_ws", category: "workstation", name: "上海工作站 01", status: "in_use", owner_id: "usr_mock_admin", location: "上海实验室 A", parent_id: "", capabilities: ["cuda", "local-build"], properties: { cpu: "Ryzen 7950X", memory: "128GB" }, updated_at: "2026-06-04T07:21:30Z" },
    { id: "ast_mock_gpu", category: "gpu", name: "RTX 4090 插槽 A", status: "in_use", owner_id: "usr_mock_admin", location: "上海实验室 A", parent_id: "ast_mock_ws", capabilities: ["cuda", "24gb-vram"], properties: { vram: "24GB" }, updated_at: "2026-06-04T07:21:40Z" },
    { id: "ast_mock_vm", category: "vm", name: "qa-runner-03", status: "available", owner_id: "usr_mock_ops", location: "10.40.7.13", parent_id: "", capabilities: ["linux", "test-runner"], properties: { os: "Ubuntu 24.04" }, updated_at: "2026-06-04T07:22:30Z" },
  ],
  environments: [
    { id: "env_mock_dev", project_id: "prj_mock_core", name: "核心 DEV", type: "DEV", status: "active", owner_id: "usr_mock_admin", member_ids: ["usr_mock_admin"], asset_ids: ["ast_mock_ws"], endpoints: [{ name: "api", url: "http://dev.opspilot.local" }], updated_at: "2026-06-04T07:23:00Z" },
    { id: "env_mock_qa", project_id: "prj_mock_core", name: "核心 QA", type: "QA", status: "active", owner_id: "usr_mock_ops", member_ids: ["usr_mock_ops"], asset_ids: ["ast_mock_vm"], endpoints: [], updated_at: "2026-06-04T07:23:30Z" },
    { id: "env_mock_qe", project_id: "prj_mock_lab", name: "实验室 QE", type: "QE", status: "inactive", owner_id: "usr_mock_ops", member_ids: [], asset_ids: [], endpoints: [], updated_at: "2026-06-04T07:24:00Z" },
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
    if (forceToast) toast("基础服务数据已刷新。");
  } catch (error) {
    state.apiOnline = false;
    state.users = clone(seed.users);
    state.projects = clone(seed.projects);
    state.assets = clone(seed.assets);
    state.environments = clone(seed.environments);
    state.auditEvents = clone(seed.auditEvents);
    if (forceToast) toast("基础服务不可用，已切换本地模拟数据。");
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
  $("#api-state").innerHTML = `${state.apiOnline ? "基础服务在线" : "本地模拟模式"} <span class="role-badge">${displayRole(state.role)}</span>`;
  $(".status-dot").classList.toggle("live", state.apiOnline);
  $("#project-switcher").innerHTML = `<option>全部项目</option>${state.projects.map((p) => `<option>${escapeHtml(p.key)} · ${escapeHtml(p.name)}</option>`).join("")}`;
  renderNav();
  document.querySelectorAll("#nav button").forEach((button) => button.classList.toggle("active", button.dataset.route === state.route));
  if (state.route === "dashboard") renderDashboard();
  if (state.route === "bigscreen") renderBigscreen();
  if (state.route === "tasks") renderTasks();
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
        <p class="eyebrow">运营工作台</p>
        <h1>运营总览</h1>
        <p class="muted">面向运维负责人：快速识别项目、资产、环境与流程风险。</p>
      </div>
    ${actionButton("create", "新建项目", "primary-button", "create-project", { type: "projects" })}
    </div>
    ${permissionBanner()}
    ${isEmpty && state.apiOnline ? `<section class="empty-state panel"><strong>实时清单为空</strong><span>请先创建用户，再创建项目、资产与环境。基础服务可访问时不会展示模拟数据。</span></section>` : ""}
    <div class="metric-grid">
      ${metric("项目总数", state.projects.length, `${linkedProjects()} 个已绑定资源`)}
      ${metric("纳管资产", state.assets.length, `${state.assets.filter((a) => a.status === "in_use").length} 个使用中`)}
      ${metric("环境实例", state.environments.length, `${readinessIssues.length} 个待修复`)}
      ${metric("用户权限", state.users.length, `${activeCount(state.users)} 个启用账号`)}
    </div>
    <div class="insight-grid">
      <section class="panel">
        <h2>风险洞察</h2>
        <p class="muted">按影响范围和紧急程度排序</p>
        ${listItems([
          `QE 性能环境缺少可用 GPU ${statusPill("high")}`,
          `GitLab 凭据 3 天后过期 ${statusPill("warning")}`,
          `项目自动化测试报告未归档 ${statusPill("warning")}`,
          `工作站 WS-309 未绑定责任人 ${statusPill("low")}`,
        ])}
      </section>
      <section class="panel">
        <h2>流程动态</h2>
        <p class="muted">智能体和人工节点的实时处理状态</p>
        ${listItems([
          `发布前巡检 ${statusPill("running")}`,
          `资产入库审批 ${statusPill("pending")}`,
          `环境容量检查 ${statusPill("done")}`,
          `异常告警复盘 ${statusPill("queued")}`,
        ])}
      </section>
    </div>
    <section class="table-wrap">
      ${overviewTable()}
    </section>
  `;
  bindActions(content);
}

function renderBigscreen() {
  content.innerHTML = `
    <section class="command-center">
      <div class="command-header">
        <h1>OpsPilot 运营指挥中心</h1>
        <span>${new Date().toLocaleString("zh-CN", { hour12: false })}</span>
      </div>
      <div class="command-grid">
        ${commandCard("项目健康度", "94.8%", "实时")}
        ${commandCard("资产在线率", "98.6%", "实时")}
        ${commandCard("环境就绪率", "87.2%", "实时")}
        ${commandCard("流程成功率", "96.1%", "实时")}
      </div>
      <div class="command-panels">
        <section class="panel">
          <h2>全国资源分布</h2>
          <p class="muted">华东、华北、华南多区域资源负载与异常热力</p>
          <div class="heat-map">${["华东", "华北", "华南", "西南", "华中", "香港", "北京", "上海", "深圳"].map((name) => `<span>${name}</span>`).join("")}</div>
        </section>
        <section class="panel">
          <h2>实时告警榜</h2>
          <p class="muted">按业务影响排序</p>
          ${listItems(["QE 集群 GPU 不足 P1", "GitLab Webhook 延迟 P2", "模型 Key 配额告警 P2", "资产盘点待确认 P3"])}
        </section>
        <section class="panel">
          <h2>流程执行趋势</h2>
          <p class="muted">近 24 小时成功、失败、人工介入走势</p>
          <p>当前运行流程 23 个<br>平均处理时长 18 分钟<br>人工介入率 7.4%</p>
          <div class="bar-row">${[92, 126, 154, 186, 218, 92, 126, 154, 186, 218, 92, 126].map((h) => `<i style="height:${h}px"></i>`).join("")}</div>
        </section>
      </div>
    </section>
  `;
}

function renderTasks() {
  content.innerHTML = `
    <div class="page-head">
      <div>
        <p class="eyebrow">运维流程</p>
        <h1>运维任务处理</h1>
        <p class="muted">处理待办、审批、智能体异常、回滚确认和执行日志，是日常操作的核心功能页。</p>
      </div>
      <button class="primary-button">批量处理</button>
    </div>
    <div class="task-layout">
      <section class="table-wrap">${taskTable()}</section>
      <aside class="detail-panel">
        <h2>任务详情</h2>
        <p class="muted">右侧面板展示上下文、处理建议、智能体结论、执行日志和提交动作</p>
        <p>建议：扩容 QE GPU 池或切换到备用环境。<br>影响：自动化性能回归流程。<br>智能体结论：当前可用 GPU 不满足需求。</p>
        <div class="action-row">
          <button class="primary-button">确认处理</button>
          <button class="ghost-button">转交他人</button>
          <button class="ghost-button danger">驳回</button>
        </div>
      </aside>
    </div>
  `;
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
      <label>本页搜索<input data-filter="localQuery" type="search" value="${escapeHtml(state.filters.localQuery || "")}" placeholder="${config.search}" /></label>
      ${config.filters.map((filter) => filterControl(filter)).join("")}
      <label>行数<select data-filter="limit"><option>10</option><option ${state.filters.limit === "25" ? "selected" : ""}>25</option></select></label>
      <button class="ghost-button" data-clear>清除</button>
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
      eyebrow: "用户权限",
      title: "用户权限",
      copy: "统一管理用户状态、平台角色与项目权限范围。",
      action: "邀请用户",
      search: "姓名、邮箱、角色",
      filters: [{ key: "status", label: "状态", values: ["all", "active", "inactive"] }],
    },
    projects: {
      eyebrow: "项目管理",
      title: "项目管理",
      copy: "项目负责人、成员、环境、资产与最近变更集中管理。",
      action: "新建项目",
      search: "项目、编号、负责人",
      filters: [{ key: "status", label: "状态", values: ["all", "active", "archived"] }],
    },
    assets: {
      eyebrow: "资产管理",
      title: "资产管理",
      copy: "服务器、GPU、VM、工作站等资产的层级、能力与责任人管理。",
      action: "登记资产",
      search: "名称、类别、位置",
      filters: [
        { key: "category", label: "类别", values: ["all", "server", "workstation", "vm", "gpu", "memory"] },
        { key: "status", label: "状态", values: ["all", "available", "in_use", "maintenance", "retired"] },
      ],
    },
    environments: {
      eyebrow: "环境管理",
      title: "环境管理",
      copy: "DEV、QA、QE 环境的责任人、端点、成员与资产绑定。",
      action: "新建环境",
      search: "环境、项目、负责人",
      filters: [
        { key: "type", label: "类型", values: ["all", "DEV", "QA", "QE"] },
        { key: "readiness", label: "就绪状态", values: ["all", "ready", "warning"] },
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
    identity: ["用户", "状态", "角色", "更新时间", "操作"],
    projects: ["项目", "负责人", "成员", "绑定", "状态", "操作"],
    assets: ["资产", "类别", "负责人", "位置", "状态", "操作"],
    environments: ["环境", "项目", "负责人", "绑定", "就绪状态", "操作"],
  }[type];
  return `<table><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => rowFor(type, row)).join("")}</tbody></table>`;
}

function rowFor(type, row) {
  if (type === "identity") return `<tr><td>${titleCell(row.id, row.name, row.email)}</td><td>${statusPill(row.status)}</td><td>${roles(row.roles)}</td><td>${date(row.updated_at)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "projects") return `<tr><td>${titleCell(row.id, `${row.key} · ${row.name}`, row.description)}</td><td>${nameFor("users", row.owner_id)}</td><td>${row.member_ids?.length || 0}</td><td>${row.environment_ids?.length || 0} env / ${row.asset_ids?.length || 0} assets</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "assets") return `<tr><td>${titleCell(row.id, row.name, row.id)}</td><td>${escapeHtml(row.category)}</td><td>${nameFor("users", row.owner_id)}</td><td>${escapeHtml(row.location || "Unassigned")}</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
  const ready = readiness(row);
  return `<tr><td>${titleCell(row.id, row.name, row.type)}</td><td>${projectName(row.project_id)}</td><td>${nameFor("users", row.owner_id)}</td><td>${row.member_ids?.length || 0} 成员 / ${row.asset_ids?.length || 0} 资产</td><td><span class="pill ${ready.level === "ok" ? "ok" : "warn"}">${ready.message}</span></td><td>${rowActions(type, row)}</td></tr>`;
}

function rowActions(type, row) {
  const statusLabel = statusActionLabel(type, row);
  return `<div class="action-row">
    ${actionButton("edit", "编辑", "ghost-button small", `edit-${type}-${row.id}`, { type, id: row.id })}
    ${statusLabel ? actionButton("status", statusLabel, "ghost-button small", `status-${type}-${row.id}`, { type, id: row.id }) : ""}
    ${actionButton("delete", "删除", "ghost-button small danger", `delete-${type}-${row.id}`, { type, id: row.id })}
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
        <div class="tab-strip"><button class="active">概览</button><button>关系</button><button>活动</button></div>
        <div class="detail-heading">
          <h2>${escapeHtml(row.name || row.key || row.email)}</h2>
          <div class="action-row">${rowActions(type, row)}</div>
        </div>
        <dl class="kv">${detailPairs(type, row).map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>
      </section>
      <aside class="detail-panel">
        <h3>关系控制</h3>
        ${relationshipControls(type, row)}
      </aside>
    </div>
  `;
}

function detailPairs(type, row) {
  const common = [["ID", escapeHtml(row.id)], ["状态", statusPill(row.status || "active")], ["更新时间", date(row.updated_at)]];
  if (type === "identity") return [["邮箱", escapeHtml(row.email)], ["角色", roles(row.roles)], ...common];
  if (type === "projects") return [["项目编号", escapeHtml(row.key)], ["负责人", nameFor("users", row.owner_id)], ["说明", escapeHtml(row.description || "暂无说明")], ["成员", String(row.member_ids?.length || 0)], ...common];
  if (type === "assets") return [["类别", escapeHtml(row.category)], ["负责人", nameFor("users", row.owner_id)], ["位置", escapeHtml(row.location || "未分配")], ["能力", tags(row.capabilities)], ["属性", escapeHtml(JSON.stringify(row.properties || {}))], ...common];
  const ready = readiness(row);
  return [["类型", escapeHtml(row.type)], ["项目", projectName(row.project_id)], ["负责人", nameFor("users", row.owner_id)], ["就绪状态", `<span class="pill ${ready.level === "ok" ? "ok" : "warn"}">${ready.message}</span>`], ["端点", String(row.endpoints?.length || 0)], ...common];
}

function relationshipControls(type, row) {
  if (state.role === "Viewer") return `<div class="permission-denied"><strong>无写入权限</strong><span>查看者可以查看关系，但不能修改绑定。</span></div>${relationshipList(type, row)}`;
  if (type === "projects") {
    const availableAssets = state.assets.filter((asset) => !(row.asset_ids || []).includes(asset.id));
    const availableEnvironments = state.environments.filter((env) => env.project_id === row.id && !(row.environment_ids || []).includes(env.id));
    return `
      <form class="inline-form" data-action="link-project-asset" data-id="${row.id}">
        <label>绑定资产<select name="asset_id">${options(availableAssets, "没有可绑定资产")}</select></label>
        <button class="ghost-button small" type="submit">绑定</button>
      </form>
      <form class="inline-form" data-action="link-project-environment" data-id="${row.id}">
        <label>绑定环境<select name="environment_id">${options(availableEnvironments, "没有可绑定环境")}</select></label>
        <button class="ghost-button small" type="submit">绑定</button>
      </form>
      <h4>已绑定资产</h4>${linkedList(row.asset_ids || [], "assets", "unlink-project-asset", row.id)}
      <h4>已绑定环境</h4>${linkedList(row.environment_ids || [], "environments", "unlink-project-environment", row.id)}
    `;
  }
  if (type === "environments") {
    const availableAssets = state.assets.filter((asset) => !(row.asset_ids || []).includes(asset.id));
    const availableMembers = state.users.filter((user) => !(row.member_ids || []).includes(user.id));
    return `
      <form class="inline-form" data-action="bind-environment-asset" data-id="${row.id}">
        <label>绑定资产<select name="asset_id">${options(availableAssets, "没有可绑定资产")}</select></label>
        <button class="ghost-button small" type="submit">绑定</button>
      </form>
      <form class="inline-form" data-action="bind-environment-member" data-id="${row.id}">
        <label>绑定成员<select name="member_id">${options(availableMembers, "没有可绑定成员")}</select></label>
        <button class="ghost-button small" type="submit">绑定</button>
      </form>
      <h4>资产</h4>${linkedList(row.asset_ids || [], "assets", "unbind-environment-asset", row.id)}
      <h4>成员</h4>${linkedList(row.member_ids || [], "users", "unbind-environment-member", row.id)}
      <h4>端点</h4>${listItems((row.endpoints || []).map((endpoint) => `端点 ${escapeHtml(endpoint.name)}: ${escapeHtml(endpoint.url)}`))}
    `;
  }
  return relationshipList(type, row);
}

function relationshipList(type, row) {
  if (type === "projects") return listItems([...(row.environment_ids || []).map(projectEnvLabel), ...(row.asset_ids || []).map(assetLabel)]);
  if (type === "assets") return listItems([row.parent_id ? `安装于 ${assetLabel(row.parent_id)}` : "无父级资产", ...state.assets.filter((asset) => asset.parent_id === row.id).map((asset) => `包含 ${escapeHtml(asset.name)}`)]);
  if (type === "environments") return listItems([...(row.member_ids || []).map((id) => `成员 ${nameFor("users", id)}`), ...(row.asset_ids || []).map((id) => `资产 ${assetLabel(id)}`), ...(row.endpoints || []).map((e) => `端点 ${escapeHtml(e.name)}: ${escapeHtml(e.url)}`)]);
  return listItems(state.projects.filter((project) => project.member_ids?.includes(row.id) || project.owner_id === row.id).map((project) => `项目 ${escapeHtml(project.key)}`));
}

function linkedList(ids, source, action, ownerId) {
  if (!ids.length) return `<div class="empty-state compact">暂无绑定记录。</div>`;
  return `<ul class="link-list">${ids.map((id) => `<li><span>${labelFor(source, id)}</span>${actionButton("link", "解绑", "ghost-button small", `${action}-${id}`, { actionName: action, id: ownerId, targetId: id })}</li>`).join("")}</ul>`;
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
  $("#modal-title").textContent = mode === "create" ? config.action : `编辑${config.title}`;
  $("#modal-body").innerHTML = formFor(type, row, mode);
  modal.showModal();
  $("#modal-body form").addEventListener("submit", (event) => submitForm(event, type, row.id));
}

function formFor(type, row, mode) {
  const userOptions = state.users.map((u) => `<option value="${u.id}" ${row.owner_id === u.id ? "selected" : ""}>${escapeHtml(u.name)}</option>`).join("");
  const projectOptions = state.projects.map((p) => `<option value="${p.id}" ${row.project_id === p.id ? "selected" : ""}>${escapeHtml(p.key)} · ${escapeHtml(p.name)}</option>`).join("");
  const assetOptions = `<option value="">无父级资产</option>${state.assets.filter((asset) => asset.id !== row.id).map((a) => `<option value="${a.id}" ${row.parent_id === a.id ? "selected" : ""}>${escapeHtml(a.name)}</option>`).join("")}`;
  const submit = mode === "create" ? resourceConfig(type).action : "保存修改";
  if (type === "identity") return `<form class="form-grid"><label>姓名<input name="name" value="${escapeAttr(row.name)}" required /></label><label>邮箱<input name="email" type="email" value="${escapeAttr(row.email)}" required /></label><label>角色<select name="role">${selectedOptions(["Admin", "Operator", "Viewer"], row.roles?.[0]?.name || "Admin")}</select></label><label>范围<select name="scope">${selectedOptions(["platform", "project"], row.roles?.[0]?.scope || "platform")}</select></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "projects") return `<form class="form-grid"><label>项目编号<input name="key" value="${escapeAttr(row.key)}" required /></label><label>项目名称<input name="name" value="${escapeAttr(row.name)}" required /></label><label>负责人<select name="owner_id" required>${userOptions}</select></label><label>状态<select name="status">${selectedOptions(["active", "archived"], row.status || "active")}</select></label><label class="full">说明<textarea name="description">${escapeHtml(row.description || "")}</textarea></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "assets") return `<form class="form-grid"><label>资产名称<input name="name" value="${escapeAttr(row.name)}" required /></label><label>类别<select name="category">${selectedOptions(["server", "workstation", "vm", "gpu", "memory"], row.category || "server")}</select></label><label>状态<select name="status">${selectedOptions(["available", "in_use", "maintenance", "retired"], row.status || "available")}</select></label><label>负责人<select name="owner_id"><option value="">未分配</option>${userOptions}</select></label><label>父级资产<select name="parent_id">${assetOptions}</select></label><label>位置<input name="location" value="${escapeAttr(row.location)}" /></label><label class="full">能力标签<input name="capabilities" value="${escapeAttr((row.capabilities || []).join(", "))}" placeholder="cuda, linux, test-runner" /></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  return `<form class="form-grid"><label>环境名称<input name="name" value="${escapeAttr(row.name)}" required /></label><label>类型<select name="type">${selectedOptions(["DEV", "QA", "QE"], row.type || "DEV")}</select></label><label>项目<select name="project_id" required>${projectOptions}</select></label><label>负责人<select name="owner_id" required>${userOptions}</select></label><label>状态<select name="status">${selectedOptions(["active", "inactive"], row.status || "active")}</select></label><label class="full">端点 URL<input name="endpoint" value="${escapeAttr(row.endpoints?.[0]?.url)}" placeholder="https://qa.example.local" /></label><button class="primary-button full" type="submit">${submit}</button></form>`;
}

async function submitForm(event, type, id) {
  event.preventDefault();
  const payload = payloadFromForm(new FormData(event.target), type);
  try {
    if (id) await mutate("PATCH", `${endpoints[type]}/${id}`, payload, type, id, (item) => ({ ...item, ...payload, updated_at: new Date().toISOString() }));
    else await mutate("POST", endpoints[type], payload, type, null, () => addLocal(type, payload));
    modal.close();
    await afterMutation(type, id);
    toast(`${resourceConfig(type).title}已保存。`);
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
  toast(`${resourceConfig(type).title}已标记为${translateStatus(nextStatus)}。`);
}

async function handleDelete(type, id) {
  if (!can("delete")) return deny("delete records");
  const item = collectionFor(type).find((row) => row.id === id);
  if (!item || !confirm(`确认删除 ${item.name || item.key || item.email}？删除后只能重新创建。`)) return;
  await mutate("DELETE", `${endpoints[type]}/${id}`, undefined, type, id, () => null);
  state.detail = null;
  await afterMutation(type);
  toast(`${resourceConfig(type).title}已删除。`);
}

async function handleRelationship(actionName, id, targetId, form) {
  if (!can("link")) return deny("change bindings");
  const value = targetId || new FormData(form).get(actionValueKey(actionName));
  if (!value) return showError("请先选择需要绑定的记录。");
  if (actionName === "link-project-asset") await mutate("POST", `/v1/projects/${id}/assets/${value}`, undefined, "projects", id, (project) => ({ ...project, asset_ids: unique([...(project.asset_ids || []), value]) }));
  if (actionName === "unlink-project-asset") await mutate("DELETE", `/v1/projects/${id}/assets/${value}`, undefined, "projects", id, (project) => ({ ...project, asset_ids: (project.asset_ids || []).filter((assetId) => assetId !== value) }));
  if (actionName === "link-project-environment") await mutate("POST", `/v1/projects/${id}/environments/${value}`, undefined, "projects", id, (project) => ({ ...project, environment_ids: unique([...(project.environment_ids || []), value]) }));
  if (actionName === "unlink-project-environment") await mutate("DELETE", `/v1/projects/${id}/environments/${value}`, undefined, "projects", id, (project) => ({ ...project, environment_ids: (project.environment_ids || []).filter((envId) => envId !== value) }));
  if (actionName === "bind-environment-asset") await patchEnvironment(id, (env) => ({ asset_ids: unique([...(env.asset_ids || []), value]) }));
  if (actionName === "unbind-environment-asset") await patchEnvironment(id, (env) => ({ asset_ids: (env.asset_ids || []).filter((assetId) => assetId !== value) }));
  if (actionName === "bind-environment-member") await patchEnvironment(id, (env) => ({ member_ids: unique([...(env.member_ids || []), value]) }));
  if (actionName === "unbind-environment-member") await patchEnvironment(id, (env) => ({ member_ids: (env.member_ids || []).filter((memberId) => memberId !== value) }));
  await afterMutation(state.route, id);
  toast("绑定关系已更新。");
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
  return `<button class="${className}" data-action="${permission}" ${attrs} ${allowed ? "" : "disabled aria-disabled=\"true\" title=\"无操作权限\""}>${label}</button>`;
}

function permissionBanner() {
  return state.role === "Viewer" ? `<section class="permission-denied"><strong>无写入权限</strong><span>查看者可浏览工作台、清单、关系与审计上下文，但创建、编辑、绑定、归档、删除操作已禁用。</span></section>` : "";
}

function deny(action) {
  toast(`无操作权限：${displayRole(state.role)}不能${action}。`);
}

function can(permission) {
  if (permission === "open") return true;
  if (state.role === "Admin") return true;
  if (state.role === "Operator") return ["create", "edit", "link"].includes(permission);
  return false;
}

function emptyStateFor(type) {
  const config = resourceConfig(type);
  const mode = state.apiOnline ? "基础服务暂无记录。" : "本地模拟数据中没有匹配记录。";
  return `<div class="empty-state"><strong>暂无${config.title}</strong><span>${mode}</span></div>`;
}

function metric(label, value, help) {
  return `<div class="metric"><span>${label}</span><strong>${value}</strong><small>${help}</small></div>`;
}

function setupCard(label, complete, help) {
  return `<section class="panel"><h3>${label} <span class="pill ${complete ? "ok" : "warn"}">${complete ? "Ready" : "Needs work"}</span></h3><p class="muted">${help}</p></section>`;
}

function activityList(events) {
  if (!events.length) return `<div class="empty-state">暂无审计事件。</div>`;
  return `<ul class="activity-list">${events.map((event) => `<li><strong>${escapeHtml(event.action)}</strong><br><span class="muted">${escapeHtml(event.resource_type)} · ${escapeHtml(event.resource_id)} · ${date(event.occurred_at)}</span></li>`).join("")}</ul>`;
}

function readiness(env) {
  const issues = [];
  if (!env.owner_id) issues.push("缺少负责人");
  if (!env.asset_ids?.length) issues.push("缺少资产");
  if (!env.endpoints?.length) issues.push("缺少端点");
  if ((env.asset_ids || []).some((id) => state.assets.find((asset) => asset.id === id)?.status === "retired")) issues.push("存在退役资产");
  return issues.length ? { level: "warn", message: issues.join("、") } : { level: "ok", message: "已就绪" };
}

function statusPill(status = "active") {
  const tone = ["active", "available", "in_use", "done"].includes(status) ? "ok" : ["inactive", "maintenance", "archived", "warning", "pending", "queued", "low"].includes(status) ? "warn" : ["high", "retired"].includes(status) ? "bad" : status === "running" ? "" : "";
  return `<span class="pill ${tone}">${escapeHtml(translateStatus(status))}</span>`;
}

function roles(value = []) {
  return value.length ? value.map((role) => `<span class="role-pill">${escapeHtml(role.scope)}:${displayRole(role.name)}</span>`).join(" ") : `<span class="muted">暂无角色</span>`;
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
  return `环境 ${escapeHtml(state.environments.find((item) => item.id === id)?.name || id)}`;
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
  return items.length ? `<ul class="link-list">${items.map((item) => `<li>${item}</li>`).join("")}</ul>` : `<div class="empty-state compact">暂无相关记录。</div>`;
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
  if (type === "identity") return row.status === "inactive" ? "启用" : "停用";
  if (type === "projects") return row.status === "archived" ? "恢复" : "归档";
  if (type === "assets") return row.status === "retired" ? "恢复" : "退役";
  if (type === "environments") return row.status === "inactive" ? "启用" : "停用";
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
  toast(`错误：${message}`);
}

function displayRole(role) {
  return { Admin: "管理员", Operator: "运维人员", Viewer: "查看者" }[role] || role;
}

function translateStatus(status) {
  return {
    active: "启用",
    inactive: "停用",
    available: "可用",
    in_use: "使用中",
    maintenance: "维护中",
    retired: "已退役",
    archived: "已归档",
    high: "高",
    warning: "中",
    low: "低",
    running: "智能体执行中",
    pending: "等待人工处理",
    done: "已完成",
    queued: "待分配",
  }[status] || status;
}

function overviewTable() {
  const rows = [
    ["智能运营中台", "王少琪", "2 个警告", "98% 在线", "10 分钟前"],
    ["自动化测试平台", "李伟", "正常", "96% 在线", "32 分钟前"],
    ["模型服务网关", "陈敏", "1 个阻塞", "99% 在线", "1 小时前"],
  ];
  return `<table><thead><tr>${["项目", "负责人", "环境健康", "资产状态", "最近变更"].map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

function taskTable() {
  const rows = [
    ["QE 环境容量不足", "环境检查", "P1", "待处理"],
    ["资产入库审批", "资产管理", "P2", "待审批"],
    ["GitLab Key 轮换", "凭据管理", "P2", "执行中"],
    ["流程失败复核", "运维流程", "P1", "待复核"],
  ];
  return `<table><thead><tr>${["任务", "来源", "优先级", "状态"].map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

function commandCard(label, value, tag) {
  return `<section class="command-card"><span>${label}</span><strong>${value}</strong><span class="pill ok">${tag}</span></section>`;
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
