const API_BASE = localStorage.getItem("opspilot_api_base") || "http://localhost:8080";
const ACTOR_ID = "web-console";
const navItems = [
  ["dashboard", "工作台"],
  ["bigscreen", "Dashboard 大屏"],
  ["tasks", "运维任务"],
  ["projects", "项目管理"],
  ["assets", "资产管理"],
  ["environments", "环境管理"],
  ["gitlabProfiles", "GitLab 集成"],
  ["vcsOperations", "VCS 操作"],
  ["vcsWebhooks", "Webhook 事件"],
  ["files", "文件中心"],
  ["testCases", "测试用例"],
  ["testSuites", "测试套件"],
  ["testRuns", "测试运行"],
  ["reports", "测试报告"],
  ["qualityGates", "质量门禁"],
  ["agents", "智能体"],
  ["skills", "Skill"],
  ["credentials", "模型 Key"],
  ["modelProviders", "模型供应商"],
  ["workflows", "运维流程"],
  ["identity", "用户权限"],
];

const collections = {
  identity: "users",
  projects: "projects",
  assets: "assets",
  environments: "environments",
  gitlabProfiles: "gitlabProfiles",
  vcsOperations: "vcsOperations",
  vcsWebhooks: "vcsWebhooks",
  files: "files",
  testCases: "testCases",
  testSuites: "testSuites",
  testRuns: "testRuns",
  reports: "reports",
  qualityGates: "qualityGates",
  agents: "agents",
  skills: "skills",
  credentials: "credentials",
  modelProviders: "modelProviders",
  workflows: "workflows",
};

const endpoints = {
  identity: "/v1/users",
  projects: "/v1/projects",
  assets: "/v1/assets",
  environments: "/v1/environments",
  gitlabProfiles: "/v1/gitlab/profiles",
  vcsOperations: "/v1/vcs/operations",
  vcsWebhooks: "/v1/vcs/webhook-events",
  files: "/v1/files",
  testCases: "/v1/test-cases",
  testSuites: "/v1/test-suites",
  testRuns: "/v1/test-runs",
  reports: "/v1/reports",
  qualityGates: "/v1/quality-gates",
  agents: "/v1/agents",
  skills: "/v1/skills",
  credentials: "/v1/credentials",
  modelProviders: "/v1/model-providers",
  workflows: "/v1/workflows",
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
  gitlabProfiles: [],
  gitlabRepositories: {},
  vcsOperations: [],
  vcsWebhooks: [],
  files: [],
  fileGrants: {},
  uploadSessions: [],
  testCases: [],
  testSuites: [],
  testRuns: [],
  reports: [],
  qualityGates: [],
  agents: [],
  skills: [],
  credentials: [],
  modelProviders: [],
  workflows: [],
  workflowVersions: {},
  workflowRuns: [],
  workflowBuilder: null,
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
  gitlabProfiles: [
    { id: "glp_mock_primary", name: "企业 GitLab 主通道", base_url: "https://gitlab.example.com", credential_ref_id: "crd_mock_gitlab", repository_selection: [{ id: "100", path: "platform/opspilot", name: "OpsPilot", web_url: "https://gitlab.example.com/platform/opspilot" }, { id: "200", path: "platform/infra", name: "Infra", web_url: "https://gitlab.example.com/platform/infra" }], status: "active", created_at: "2026-06-04T08:00:00Z", updated_at: "2026-06-04T08:00:00Z" },
  ],
  gitlabRepositories: {
    glp_mock_primary: [
      { id: "100", path: "platform/opspilot", name: "OpsPilot", web_url: "https://gitlab.example.com/platform/opspilot" },
      { id: "200", path: "platform/infra", name: "Infra", web_url: "https://gitlab.example.com/platform/infra" },
    ],
  },
  vcsOperations: [
    { id: "vcs_mock_branch", provider: "gitlab", profile_id: "glp_mock_primary", repository_id: "100", operation_type: "create_branch", branch: "release/qa-ready", source_branch: "", target_branch: "", title: "", external_id: "local-branch-100", status: "completed", result: { repository_path: "platform/opspilot" }, created_at: "2026-06-04T08:10:00Z", updated_at: "2026-06-04T08:10:00Z" },
  ],
  vcsWebhooks: [
    { id: "whk_mock_pipeline", provider: "gitlab", profile_id: "glp_mock_primary", repository_id: "100", event_type: "Pipeline Hook", payload: { status: "success", ref: "main" }, status: "received", created_at: "2026-06-04T08:11:00Z", updated_at: "2026-06-04T08:11:00Z" },
  ],
  files: [
    { id: "fil_mock_report", filename: "qa-regression-report.pdf", content_type: "application/pdf", size_bytes: 524288, owner_id: "usr_mock_ops", status: "available", checksum: "sha256:mock", created_at: "2026-06-04T08:12:00Z", updated_at: "2026-06-04T08:12:00Z" },
  ],
  fileGrants: {},
  uploadSessions: [],
  testCases: [
    { id: "tca_mock_login", project_id: "prj_mock_core", name: "登录鉴权冒烟", case_type: "automated", priority: "high", status: "active", steps: [{ name: "登录", expected: "进入控制台" }], created_at: "2026-06-04T08:13:00Z", updated_at: "2026-06-04T08:13:00Z" },
  ],
  testSuites: [
    { id: "tsu_mock_regression", project_id: "prj_mock_core", name: "核心回归套件", case_ids: ["tca_mock_login"], status: "active", created_at: "2026-06-04T08:14:00Z", updated_at: "2026-06-04T08:14:00Z" },
  ],
  testRuns: [
    { id: "trn_mock_nightly", project_id: "prj_mock_core", suite_id: "tsu_mock_regression", environment_id: "env_mock_qa", status: "passed", results: [{ case_id: "tca_mock_login", status: "passed" }], created_at: "2026-06-04T08:15:00Z", updated_at: "2026-06-04T08:15:00Z" },
  ],
  reports: [
    { id: "rpt_mock_qa", project_id: "prj_mock_core", title: "QA 夜间回归报告", report_type: "qa", test_run_id: "trn_mock_nightly", file_ids: ["fil_mock_report"], summary: { passed: 18, failed: 0 }, status: "published", created_at: "2026-06-04T08:16:00Z", updated_at: "2026-06-04T08:16:00Z" },
  ],
  qualityGates: [
    { id: "qgt_mock_release", project_id: "prj_mock_core", name: "发布准入门禁", conditions: [{ metric: "failed", operator: "=", value: 0 }], last_report_id: "rpt_mock_qa", status: "passed", created_at: "2026-06-04T08:17:00Z", updated_at: "2026-06-04T08:17:00Z" },
  ],
  skills: [
    { id: "skl_mock_release", name: "发布前巡检", version: "1.0.0", runtime: "python", description: "检查环境就绪、资产绑定与测试报告状态。", status: "active", capabilities: ["readiness", "report"], package_file_id: "", created_at: "2026-06-04T08:01:00Z", updated_at: "2026-06-04T08:01:00Z" },
    { id: "skl_mock_asset", name: "资产盘点", version: "1.1.0", runtime: "node", description: "同步资产标签、责任人与容量信息。", status: "active", capabilities: ["inventory", "audit"], package_file_id: "", created_at: "2026-06-04T08:02:00Z", updated_at: "2026-06-04T08:02:00Z" },
  ],
  credentials: [
    { id: "crd_mock_deepseek", provider: "model_provider", name: "DeepSeek 企业 Key", secret_ref: "vault://local/mock/deepseek", secret_fingerprint: "fp_mock_8f2a", status: "active", created_at: "2026-06-04T08:03:00Z", updated_at: "2026-06-04T08:03:00Z" },
    { id: "crd_mock_gitlab", provider: "gitlab", name: "GitLab 企业 Token", secret_ref: "vault://local/mock/gitlab", secret_fingerprint: "fp_mock_gitlab", status: "active", created_at: "2026-06-04T08:03:30Z", updated_at: "2026-06-04T08:03:30Z" },
  ],
  modelProviders: [
    { id: "mdl_mock_deepseek", provider: "deepseek", name: "DeepSeek 生产通道", credential_ref_id: "crd_mock_deepseek", base_url: "https://api.deepseek.com", models: ["deepseek-chat", "deepseek-reasoner"], status: "active", created_at: "2026-06-04T08:04:00Z", updated_at: "2026-06-04T08:04:00Z" },
  ],
  agents: [
    { id: "agt_mock_ops", name: "运维总控智能体", kind: "ops_controller", description: "编排巡检、审批与回滚建议。", status: "active", capabilities: ["workflow", "incident"], skill_ids: ["skl_mock_release", "skl_mock_asset"], model_provider_id: "mdl_mock_deepseek", created_at: "2026-06-04T08:05:00Z", updated_at: "2026-06-04T08:05:00Z" },
  ],
  workflows: [
    { id: "wfl_mock_release", name: "发布前自动巡检", description: "面向 QA/QE 环境的发布前检查流程。", project_id: "prj_mock_core", status: "active", active_version_id: "wfv_mock_release_v1", created_at: "2026-06-04T08:06:00Z", updated_at: "2026-06-04T08:06:00Z" },
  ],
  workflowVersions: {
    wfl_mock_release: [
      { id: "wfv_mock_release_v1", workflow_id: "wfl_mock_release", version: "1", status: "active", nodes: [{ id: "trigger", type: "trigger", name: "发布触发" }, { id: "agent-check", type: "agent_task", name: "智能体巡检", agent_id: "agt_mock_ops", skill_id: "skl_mock_release", model_provider_id: "mdl_mock_deepseek" }, { id: "approval", type: "approval", name: "人工确认" }, { id: "release-result", type: "result", name: "发布结论" }], edges: [{ from_node_id: "trigger", to_node_id: "agent-check" }, { from_node_id: "agent-check", to_node_id: "approval" }, { from_node_id: "approval", to_node_id: "release-result" }], created_at: "2026-06-04T08:07:00Z", updated_at: "2026-06-04T08:07:00Z" },
    ],
  },
  workflowRuns: [
    {
      id: "wfr_mock_release_1",
      workflow_id: "wfl_mock_release",
      workflow_version_id: "wfv_mock_release_v1",
      trigger_type: "manual",
      status: "running",
      started_at: "2026-06-04T08:22:00Z",
      created_at: "2026-06-04T08:20:00Z",
      updated_at: "2026-06-04T08:24:00Z",
      steps: [
        { id: "wfs_mock_trigger", workflow_run_id: "wfr_mock_release_1", workflow_id: "wfl_mock_release", workflow_version_id: "wfv_mock_release_v1", node_id: "trigger", node_type: "trigger", step_type: "trigger", sequence: 1, name: "发布触发", predecessor_node_ids: [], status: "completed", output: { trigger: "manual" }, created_at: "2026-06-04T08:20:00Z", updated_at: "2026-06-04T08:22:00Z", started_at: "2026-06-04T08:22:00Z", completed_at: "2026-06-04T08:22:00Z" },
        { id: "wfs_mock_agent", workflow_run_id: "wfr_mock_release_1", workflow_id: "wfl_mock_release", workflow_version_id: "wfv_mock_release_v1", node_id: "agent-check", node_type: "agent_task", step_type: "agent", sequence: 2, name: "智能体巡检", agent_id: "agt_mock_ops", skill_id: "skl_mock_release", model_provider_id: "mdl_mock_deepseek", predecessor_node_ids: ["trigger"], status: "completed", output: { summary: "QA 环境就绪，质量门禁通过。" }, created_at: "2026-06-04T08:20:00Z", updated_at: "2026-06-04T08:23:00Z", started_at: "2026-06-04T08:22:20Z", completed_at: "2026-06-04T08:23:00Z" },
        { id: "wfs_mock_approval", workflow_run_id: "wfr_mock_release_1", workflow_id: "wfl_mock_release", workflow_version_id: "wfv_mock_release_v1", node_id: "approval", node_type: "approval", step_type: "manual", sequence: 3, name: "人工确认", predecessor_node_ids: ["agent-check"], status: "pending", created_at: "2026-06-04T08:20:00Z", updated_at: "2026-06-04T08:24:00Z" },
        { id: "wfs_mock_result", workflow_run_id: "wfr_mock_release_1", workflow_id: "wfl_mock_release", workflow_version_id: "wfv_mock_release_v1", node_id: "release-result", node_type: "result", step_type: "result", sequence: 4, name: "发布结论", predecessor_node_ids: ["approval"], status: "pending", created_at: "2026-06-04T08:20:00Z", updated_at: "2026-06-04T08:24:00Z" },
      ],
    },
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
    const [users, projects, assets, environments, gitlabProfiles, vcsOperations, vcsWebhooks, files, testCases, testSuites, testRuns, reports, qualityGates, agents, skills, credentials, modelProviders, workflows, workflowRuns, auditEvents] = await Promise.all([
      apiGet("/v1/users"),
      apiGet("/v1/projects"),
      apiGet("/v1/assets"),
      apiGet("/v1/environments"),
      apiGet("/v1/gitlab/profiles"),
      apiGet("/v1/vcs/operations"),
      apiGet("/v1/vcs/webhook-events"),
      apiGet("/v1/files"),
      apiGet("/v1/test-cases"),
      apiGet("/v1/test-suites"),
      apiGet("/v1/test-runs"),
      apiGet("/v1/reports"),
      apiGet("/v1/quality-gates"),
      apiGet("/v1/agents"),
      apiGet("/v1/skills"),
      apiGet("/v1/credentials"),
      apiGet("/v1/model-providers"),
      apiGet("/v1/workflows"),
      apiGet("/v1/workflow-runs"),
      apiGet("/v1/audit-events"),
    ]);
    const workflowVersions = {};
    await Promise.all(workflows.map(async (workflow) => {
      workflowVersions[workflow.id] = await apiGet(`/v1/workflows/${workflow.id}/versions`);
    }));
    const gitlabRepositories = {};
    await Promise.all(gitlabProfiles.map(async (profile) => {
      gitlabRepositories[profile.id] = await apiGet(`/v1/gitlab/profiles/${profile.id}/repositories`);
    }));
    state.apiOnline = true;
    state.users = users;
    state.projects = projects;
    state.assets = assets;
    state.environments = environments;
    state.gitlabProfiles = gitlabProfiles.map(sanitizeGitLabProfile);
    state.gitlabRepositories = sanitizeGitLabRepositoryMap(gitlabRepositories);
    state.vcsOperations = vcsOperations;
    state.vcsWebhooks = vcsWebhooks.map(sanitizeWebhookEvent);
    state.files = files;
    state.fileGrants = {};
    state.uploadSessions = [];
    state.testCases = testCases;
    state.testSuites = testSuites;
    state.testRuns = testRuns;
    state.reports = reports;
    state.qualityGates = qualityGates;
    state.agents = agents;
    state.skills = skills;
    state.credentials = credentials.map((credential) => sanitizeCredential(credential));
    state.modelProviders = modelProviders;
    state.workflows = workflows;
    state.workflowVersions = workflowVersions;
    state.workflowRuns = workflowRuns;
    state.auditEvents = auditEvents;
    if (forceToast) toast("基础服务数据已刷新。");
  } catch (error) {
    state.apiOnline = false;
    state.users = clone(seed.users);
    state.projects = clone(seed.projects);
    state.assets = clone(seed.assets);
    state.environments = clone(seed.environments);
    state.gitlabProfiles = clone(seed.gitlabProfiles).map(sanitizeGitLabProfile);
    state.gitlabRepositories = sanitizeGitLabRepositoryMap(clone(seed.gitlabRepositories));
    state.vcsOperations = clone(seed.vcsOperations);
    state.vcsWebhooks = clone(seed.vcsWebhooks).map(sanitizeWebhookEvent);
    state.files = clone(seed.files);
    state.fileGrants = clone(seed.fileGrants);
    state.uploadSessions = clone(seed.uploadSessions);
    state.testCases = clone(seed.testCases);
    state.testSuites = clone(seed.testSuites);
    state.testRuns = clone(seed.testRuns);
    state.reports = clone(seed.reports);
    state.qualityGates = clone(seed.qualityGates);
    state.agents = clone(seed.agents);
    state.skills = clone(seed.skills);
    state.credentials = clone(seed.credentials).map((credential) => sanitizeCredential(credential));
    state.modelProviders = clone(seed.modelProviders);
    state.workflows = clone(seed.workflows);
    state.workflowVersions = clone(seed.workflowVersions);
    state.workflowRuns = clone(seed.workflowRuns);
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
    state.workflowBuilder = null;
    render();
  };
}

function render() {
  document.body.classList.toggle("bigscreen-mode", state.route === "bigscreen");
  document.body.classList.toggle("builder-mode", state.route === "workflows" && Boolean(state.workflowBuilder));
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
  if (state.route === "gitlabProfiles") renderResource("gitlabProfiles");
  if (state.route === "vcsOperations") renderResource("vcsOperations");
  if (state.route === "vcsWebhooks") renderResource("vcsWebhooks");
  if (state.route === "files") renderResource("files");
  if (state.route === "testCases") renderResource("testCases");
  if (state.route === "testSuites") renderResource("testSuites");
  if (state.route === "testRuns") renderResource("testRuns");
  if (state.route === "reports") renderResource("reports");
  if (state.route === "qualityGates") renderResource("qualityGates");
  if (state.route === "agents") renderResource("agents");
  if (state.route === "skills") renderResource("skills");
  if (state.route === "credentials") renderResource("credentials");
  if (state.route === "modelProviders") renderResource("modelProviders");
  if (state.route === "workflows") state.workflowBuilder ? renderWorkflowBuilder() : renderResource("workflows");
}

function renderDashboard() {
  const readinessIssues = state.environments.filter((env) => readiness(env).level !== "ok");
  const isEmpty = !state.users.length && !state.projects.length && !state.assets.length && !state.environments.length;
  const overview = overviewTable();
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
    ${overview ? `<section class="table-wrap">${overview}</section>` : ""}
  `;
  bindActions(content);
}

function renderBigscreen() {
  content.innerHTML = `
    <section class="command-center">
      <div class="command-header">
        <h1>OpsPilot 运营指挥中心</h1>
        <div class="command-actions">
          <span>${new Date().toLocaleString("zh-CN", { hour12: false })}</span>
          <button class="ghost-button" data-action="return-dashboard">返回控制台</button>
        </div>
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
  content.querySelector("[data-action='return-dashboard']").addEventListener("click", () => {
    state.route = "dashboard";
    render();
  });
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
      <section class="table-wrap task-table-wrap">${taskTable()}</section>
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
    gitlabProfiles: {
      eyebrow: "GitLab 集成",
      title: "GitLab 集成",
      copy: "配置 GitLab API Profile、仓库选择与项目绑定，凭据只以安全引用保存。",
      action: "新增 GitLab 通道",
      search: "Profile、Base URL、仓库、凭据",
      filters: [{ key: "status", label: "状态", values: ["all", "active", "inactive"] }],
    },
    vcsOperations: {
      eyebrow: "VCS 操作",
      title: "VCS 操作",
      copy: "跟踪分支创建、Merge Request 与合并动作的本地适配器执行记录。",
      action: "发起 VCS 操作",
      search: "仓库、分支、标题、状态",
      filters: [
        { key: "operation_type", label: "操作", values: ["all", "create_branch", "open_merge_request", "merge_merge_request"] },
        { key: "status", label: "状态", values: ["all", "queued", "completed", "failed"] },
      ],
    },
    vcsWebhooks: {
      eyebrow: "VCS 事件",
      title: "Webhook 事件",
      copy: "查看和验证 GitLab Webhook 事件，提交时需要一次性 authenticity token，落库前会按后端规则脱敏。",
      action: "登记 Webhook",
      search: "事件、仓库、Profile、状态",
      filters: [{ key: "status", label: "状态", values: ["all", "received", "processed", "rejected"] }],
    },
    files: {
      eyebrow: "文件中心",
      title: "文件中心",
      copy: "登记上传对象、生成上传/下载授权、完成上传会话，为报告和 Skill 包提供文件引用。",
      action: "登记文件",
      search: "文件名、类型、校验和、状态",
      filters: [{ key: "status", label: "状态", values: ["all", "pending_upload", "available", "deleted"] }],
    },
    testCases: {
      eyebrow: "测试中心",
      title: "测试用例",
      copy: "维护项目级手工/自动化用例、优先级与步骤摘要。",
      action: "新增用例",
      search: "用例、项目、类型、优先级",
      filters: [
        { key: "case_type", label: "类型", values: ["all", "manual", "automated"] },
        { key: "status", label: "状态", values: ["all", "active", "inactive"] },
      ],
    },
    testSuites: {
      eyebrow: "测试中心",
      title: "测试套件",
      copy: "按项目组织用例集合，为测试运行和质量报告提供输入。",
      action: "新增套件",
      search: "套件、项目、用例",
      filters: [{ key: "status", label: "状态", values: ["all", "active", "inactive"] }],
    },
    testRuns: {
      eyebrow: "测试中心",
      title: "测试运行",
      copy: "创建并跟踪环境中的套件执行状态、结果摘要与报告链路。",
      action: "发起测试运行",
      search: "运行、项目、套件、环境、状态",
      filters: [{ key: "status", label: "状态", values: ["all", "queued", "running", "passed", "failed", "cancelled"] }],
    },
    reports: {
      eyebrow: "测试报告",
      title: "测试报告",
      copy: "归档测试、QA/QE 与运维报告，关联测试运行和文件中心对象。",
      action: "新增报告",
      search: "报告、项目、类型、状态",
      filters: [{ key: "report_type", label: "类型", values: ["all", "test", "qa", "qe", "operations"] }],
    },
    qualityGates: {
      eyebrow: "测试报告",
      title: "质量门禁",
      copy: "维护项目发布准入条件、最近报告与门禁结论。",
      action: "新增门禁",
      search: "门禁、项目、状态、条件",
      filters: [{ key: "status", label: "状态", values: ["all", "pending", "passed", "failed", "waived"] }],
    },
    agents: {
      eyebrow: "智能体管理",
      title: "智能体",
      copy: "登记智能体类型、能力、关联 Skill 与模型供应商，为流程编排提供可控执行单元。",
      action: "新建智能体",
      search: "智能体、类型、能力",
      filters: [{ key: "status", label: "状态", values: ["all", "active", "inactive"] }],
    },
    skills: {
      eyebrow: "Skill 目录",
      title: "Skill",
      copy: "管理可复用技能包、运行时、版本与能力标签，供智能体和流程节点引用。",
      action: "登记 Skill",
      search: "名称、版本、运行时、能力",
      filters: [
        { key: "runtime", label: "运行时", values: ["all", "python", "node", "shell", "container"] },
        { key: "status", label: "状态", values: ["all", "active", "deprecated"] },
      ],
    },
    credentials: {
      eyebrow: "模型 Key",
      title: "模型 Key",
      copy: "通过安全凭据引用接入模型 API Key；页面不展示原始密钥，只维护可审计引用。",
      action: "新增模型 Key",
      search: "名称、指纹、状态",
      filters: [{ key: "status", label: "状态", values: ["all", "active", "inactive"] }],
    },
    modelProviders: {
      eyebrow: "模型供应商",
      title: "模型供应商",
      copy: "配置模型提供方、Base URL、可用模型与安全 credential ref。",
      action: "新增供应商",
      search: "供应商、名称、模型",
      filters: [{ key: "status", label: "状态", values: ["all", "active", "inactive"] }],
    },
    workflows: {
      eyebrow: "流程定义",
      title: "运维流程定义",
      copy: "维护流程定义、项目归属、版本、节点和边，为智能体参与运维提供结构化蓝图。",
      action: "新建流程",
      search: "流程、项目、状态",
      filters: [{ key: "status", label: "状态", values: ["all", "draft", "active", "archived"] }],
    },
  }[type];
}

function filteredRows(type) {
  const map = { identity: state.users, projects: state.projects, assets: state.assets, environments: state.environments, gitlabProfiles: state.gitlabProfiles, vcsOperations: state.vcsOperations, vcsWebhooks: state.vcsWebhooks, files: state.files, testCases: state.testCases, testSuites: state.testSuites, testRuns: state.testRuns, reports: state.reports, qualityGates: state.qualityGates, agents: state.agents, skills: state.skills, credentials: state.credentials.filter((row) => row.provider === "model_provider"), modelProviders: state.modelProviders, workflows: state.workflows };
  const query = [state.query, state.filters.localQuery].filter(Boolean).join(" ").toLowerCase();
  return map[type].filter((row) => {
    const text = JSON.stringify(searchableRow(type, row)).toLowerCase();
    if (query && !query.split(/\s+/).every((token) => text.includes(token))) return false;
    if (type === "assets" && state.filters.category && state.filters.category !== "all" && row.category !== state.filters.category) return false;
    if ((type === "identity" || type === "projects" || type === "assets") && state.filters.status && state.filters.status !== "all" && row.status !== state.filters.status) return false;
    if (["gitlabProfiles", "vcsOperations", "vcsWebhooks", "files", "testCases", "testSuites", "testRuns", "qualityGates", "agents", "skills", "credentials", "modelProviders", "workflows"].includes(type) && state.filters.status && state.filters.status !== "all" && row.status !== state.filters.status) return false;
    if (type === "vcsOperations" && state.filters.operation_type && state.filters.operation_type !== "all" && row.operation_type !== state.filters.operation_type) return false;
    if (type === "testCases" && state.filters.case_type && state.filters.case_type !== "all" && row.case_type !== state.filters.case_type) return false;
    if (type === "reports" && state.filters.report_type && state.filters.report_type !== "all" && row.report_type !== state.filters.report_type) return false;
    if (type === "skills" && state.filters.runtime && state.filters.runtime !== "all" && row.runtime !== state.filters.runtime) return false;
    if (type === "environments" && state.filters.type && state.filters.type !== "all" && row.type !== state.filters.type) return false;
    if (type === "environments" && state.filters.readiness && state.filters.readiness !== "all") {
      const ready = readiness(row).level === "ok" ? "ready" : "warning";
      if (ready !== state.filters.readiness) return false;
    }
    return true;
  }).slice(0, Number(state.filters.limit || 10));
}

function searchableRow(type, row) {
  if (type === "gitlabProfiles") return sanitizeGitLabProfile(row);
  if (type === "vcsWebhooks") return sanitizeWebhookEvent(row);
  return type === "credentials" ? sanitizeCredential(row) : row;
}

function tableFor(type, rows) {
  const headers = {
    identity: ["用户", "状态", "角色", "更新时间", "操作"],
    projects: ["项目", "负责人", "成员", "绑定", "状态", "操作"],
    assets: ["资产", "类别", "负责人", "位置", "状态", "操作"],
    environments: ["环境", "项目", "负责人", "绑定", "就绪状态", "操作"],
    gitlabProfiles: ["Profile", "Base URL", "凭据", "仓库", "状态", "操作"],
    vcsOperations: ["操作", "仓库", "分支/MR", "结果", "状态", "操作"],
    vcsWebhooks: ["事件", "Profile", "仓库", "Payload", "状态", "操作"],
    files: ["文件", "类型", "大小", "上传", "状态", "操作"],
    testCases: ["用例", "项目", "类型", "优先级", "状态", "操作"],
    testSuites: ["套件", "项目", "用例数", "状态", "更新时间", "操作"],
    testRuns: ["运行", "项目", "套件", "环境", "状态", "操作"],
    reports: ["报告", "项目", "类型", "关联", "状态", "操作"],
    qualityGates: ["门禁", "项目", "条件", "最近报告", "状态", "操作"],
    agents: ["智能体", "类型", "能力", "Skill", "模型", "状态", "操作"],
    skills: ["Skill", "运行时", "能力", "包文件", "状态", "操作"],
    credentials: ["模型 Key", "密钥引用", "指纹", "状态", "操作"],
    modelProviders: ["供应商", "凭据", "模型", "Base URL", "状态", "操作"],
    workflows: ["流程", "项目", "版本", "节点", "运行", "状态", "操作"],
  }[type];
  return `<table><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => rowFor(type, row)).join("")}</tbody></table>`;
}

function rowFor(type, row) {
  if (type === "identity") return `<tr><td>${titleCell(row.id, row.name, row.email)}</td><td>${statusPill(row.status)}</td><td>${roles(row.roles)}</td><td>${date(row.updated_at)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "projects") return `<tr><td>${titleCell(row.id, `${row.key} · ${row.name}`, row.description)}</td><td>${nameFor("users", row.owner_id)}</td><td>${row.member_ids?.length || 0}</td><td>${row.environment_ids?.length || 0} env / ${row.asset_ids?.length || 0} assets</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "assets") return `<tr><td>${titleCell(row.id, row.name, row.id)}</td><td>${escapeHtml(row.category)}</td><td>${nameFor("users", row.owner_id)}</td><td>${escapeHtml(row.location || "Unassigned")}</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "environments") {
    const ready = readiness(row);
    return `<tr><td>${titleCell(row.id, row.name, row.type)}</td><td>${projectName(row.project_id)}</td><td>${nameFor("users", row.owner_id)}</td><td>${row.member_ids?.length || 0} 成员 / ${row.asset_ids?.length || 0} 资产</td><td><span class="pill ${ready.level === "ok" ? "ok" : "warn"}">${ready.message}</span></td><td>${rowActions(type, row)}</td></tr>`;
  }
  if (type === "gitlabProfiles") return `<tr><td>${titleCell(row.id, row.name, row.id)}</td><td>${escapeHtml(row.base_url)}</td><td>${credentialName(row.credential_ref_id)}</td><td>${(state.gitlabRepositories[row.id] || row.repository_selection || []).length}</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "vcsOperations") return `<tr><td>${titleCell(row.id, translateOperation(row.operation_type), row.external_id || row.id)}</td><td>${repositoryName(row.profile_id, row.repository_id)}</td><td>${escapeHtml(row.branch || `${row.source_branch || "-"} -> ${row.target_branch || "-"}`)}</td><td>${escapeHtml(row.result?.repository_path || row.result?.web_url || "本地适配器")}</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "vcsWebhooks") return `<tr><td>${titleCell(row.id, row.event_type, row.id)}</td><td>${gitlabProfileName(row.profile_id)}</td><td>${repositoryName(row.profile_id, row.repository_id)}</td><td>${escapeHtml(Object.keys(row.payload || {}).join(", ") || "无")}</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "files") return `<tr><td>${titleCell(row.id, row.filename, row.checksum || row.id)}</td><td>${escapeHtml(row.content_type)}</td><td>${formatBytes(row.size_bytes)}</td><td>${fileUploadState(row)}</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "testCases") return `<tr><td>${titleCell(row.id, row.name, `${translateStatus(row.priority)} · ${row.id}`)}</td><td>${projectName(row.project_id)}</td><td>${escapeHtml(row.case_type)}</td><td>${statusPill(row.priority)}</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "testSuites") return `<tr><td>${titleCell(row.id, row.name, row.id)}</td><td>${projectName(row.project_id)}</td><td>${row.case_ids?.length || 0}</td><td>${statusPill(row.status)}</td><td>${date(row.updated_at)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "testRuns") return `<tr><td>${titleCell(row.id, `运行 ${row.id}`, row.results?.length ? `${row.results.length} 条结果` : "暂无结果")}</td><td>${projectName(row.project_id)}</td><td>${testSuiteName(row.suite_id)}</td><td>${environmentName(row.environment_id)}</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "reports") return `<tr><td>${titleCell(row.id, row.title, row.id)}</td><td>${projectName(row.project_id)}</td><td>${escapeHtml(row.report_type)}</td><td>${row.file_ids?.length || 0} 文件 / ${row.test_run_id ? "1 运行" : "无运行"}</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "qualityGates") return `<tr><td>${titleCell(row.id, row.name, row.id)}</td><td>${projectName(row.project_id)}</td><td>${row.conditions?.length || 0}</td><td>${reportName(row.last_report_id)}</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "agents") return `<tr><td>${titleCell(row.id, row.name, row.description)}</td><td>${escapeHtml(row.kind)}</td><td>${tags(row.capabilities)}</td><td>${row.skill_ids?.length || 0}</td><td>${modelProviderName(row.model_provider_id)}</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "skills") return `<tr><td>${titleCell(row.id, `${row.name} · ${row.version}`, row.description)}</td><td>${escapeHtml(row.runtime)}</td><td>${tags(row.capabilities)}</td><td>${escapeHtml(row.package_file_id || "未绑定")}</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "credentials") return `<tr><td>${titleCell(row.id, row.name, "provider:model_provider")}</td><td>${escapeHtml(row.secret_ref || "安全引用")}</td><td>${escapeHtml(row.secret_fingerprint || "未生成")}</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
  if (type === "modelProviders") return `<tr><td>${titleCell(row.id, row.name, row.provider)}</td><td>${credentialName(row.credential_ref_id)}</td><td>${tags(row.models)}</td><td>${escapeHtml(row.base_url || "默认")}</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
  const versions = state.workflowVersions[row.id] || [];
  return `<tr><td>${titleCell(row.id, row.name, row.description)}</td><td>${projectName(row.project_id)}</td><td>${versions.length} 个版本</td><td>${workflowNodeCount(row.id)} 个节点</td><td>${workflowRunsFor(row.id).length} 次</td><td>${statusPill(row.status)}</td><td>${rowActions(type, row)}</td></tr>`;
}

function rowActions(type, row) {
  const statusLabel = statusActionLabel(type, row);
  if (type === "workflows") return `<div class="action-row">
    ${actionButton("open", "详情", "ghost-button small", `open-${type}-${row.id}`, { id: row.id, type })}
    ${actionButton("link", "创建并启动", "ghost-button small", `run-${row.id}`, { actionName: "create-start-workflow-run", id: row.id })}
    ${actionButton("link", "编辑画布", "primary-button small", `builder-${row.id}`, { actionName: "open-workflow-builder", id: row.id })}
    ${actionButton("edit", "编辑", "ghost-button small", `edit-${type}-${row.id}`, { type, id: row.id })}
    ${statusLabel ? actionButton("status", statusLabel, "ghost-button small", `status-${type}-${row.id}`, { type, id: row.id }) : ""}
    ${supportsDelete(type) ? actionButton("delete", "删除", "ghost-button small danger", `delete-${type}-${row.id}`, { type, id: row.id }) : ""}
  </div>`;
  if (type === "files") return `<div class="action-row">
    ${actionButton("open", "详情", "ghost-button small", `open-${type}-${row.id}`, { id: row.id, type })}
    ${actionButton("link", "上传授权", "ghost-button small", `upload-grant-${row.id}`, { actionName: "create-upload-grant", id: row.id })}
    ${actionButton("link", "上传会话", "ghost-button small", `upload-session-${row.id}`, { actionName: "create-upload-session", id: row.id })}
    ${actionButton("link", "完成上传", "ghost-button small", `complete-upload-${row.id}`, { actionName: "complete-upload-session", id: row.id })}
    ${actionButton("link", "下载授权", "ghost-button small", `download-grant-${row.id}`, { actionName: "create-download-grant", id: row.id })}
  </div>`;
  if (!supportsEdit(type) && !supportsDelete(type) && !statusLabel) return `<div class="action-row">${actionButton("open", "详情", "ghost-button small", `open-${type}-${row.id}`, { id: row.id, type })}</div>`;
  return `<div class="action-row">
    ${actionButton("edit", "编辑", "ghost-button small", `edit-${type}-${row.id}`, { type, id: row.id })}
    ${statusLabel ? actionButton("status", statusLabel, "ghost-button small", `status-${type}-${row.id}`, { type, id: row.id }) : ""}
    ${supportsDelete(type) ? actionButton("delete", "删除", "ghost-button small danger", `delete-${type}-${row.id}`, { type, id: row.id }) : ""}
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
          <h2>${escapeHtml(displayTitle(type, row))}</h2>
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
  if (type === "assets") return [["类别", escapeHtml(row.category)], ["负责人", nameFor("users", row.owner_id)], ["位置", escapeHtml(row.location || "未分配")], ["能力", tags(row.capabilities)], ["属性", jsonBlock(row.properties || {})], ...common];
  if (type === "environments") {
    const ready = readiness(row);
    return [["类型", escapeHtml(row.type)], ["项目", projectName(row.project_id)], ["负责人", nameFor("users", row.owner_id)], ["就绪状态", `<span class="pill ${ready.level === "ok" ? "ok" : "warn"}">${ready.message}</span>`], ["端点", String(row.endpoints?.length || 0)], ...common];
  }
  if (type === "gitlabProfiles") return [["Base URL", escapeHtml(row.base_url)], ["Credential", credentialName(row.credential_ref_id)], ["仓库选择", String((state.gitlabRepositories[row.id] || row.repository_selection || []).length)], ...common];
  if (type === "vcsOperations") return [["Profile", gitlabProfileName(row.profile_id)], ["仓库", repositoryName(row.profile_id, row.repository_id)], ["操作", escapeHtml(translateOperation(row.operation_type))], ["分支", escapeHtml(row.branch || "-")], ["Source", escapeHtml(row.source_branch || "-")], ["Target", escapeHtml(row.target_branch || "-")], ["标题", escapeHtml(row.title || "-")], ["结果", jsonBlock(row.result || {})], ...common];
  if (type === "vcsWebhooks") return [["Profile", gitlabProfileName(row.profile_id)], ["仓库", repositoryName(row.profile_id, row.repository_id)], ["事件", escapeHtml(row.event_type)], ["Payload", jsonBlock(sanitizeWebhookEvent(row).payload || {})], ...common];
  if (type === "files") return [["文件名", escapeHtml(row.filename)], ["Content-Type", escapeHtml(row.content_type)], ["大小", formatBytes(row.size_bytes)], ["Checksum", escapeHtml(row.checksum || "未记录")], ["Owner", nameFor("users", row.owner_id)], ["授权/会话", fileGrantSummary(row.id)], ...common];
  if (type === "testCases") return [["项目", projectName(row.project_id)], ["类型", escapeHtml(row.case_type)], ["优先级", statusPill(row.priority)], ["步骤", String(row.steps?.length || 0)], ...common];
  if (type === "testSuites") return [["项目", projectName(row.project_id)], ["用例", linkedNameList(row.case_ids || [], "testCases")], ...common];
  if (type === "testRuns") return [["项目", projectName(row.project_id)], ["套件", testSuiteName(row.suite_id)], ["环境", environmentName(row.environment_id)], ["结果", jsonBlock(row.results || [])], ...common];
  if (type === "reports") return [["项目", projectName(row.project_id)], ["类型", escapeHtml(row.report_type)], ["测试运行", testRunName(row.test_run_id)], ["文件", linkedNameList(row.file_ids || [], "files")], ["摘要", jsonBlock(row.summary || {})], ...common];
  if (type === "qualityGates") return [["项目", projectName(row.project_id)], ["最近报告", reportName(row.last_report_id)], ["条件", jsonBlock(row.conditions || [])], ...common];
  if (type === "agents") return [["类型", escapeHtml(row.kind)], ["说明", escapeHtml(row.description || "暂无说明")], ["能力", tags(row.capabilities)], ["关联 Skill", linkedNameList(row.skill_ids || [], "skills")], ["模型供应商", modelProviderName(row.model_provider_id)], ...common];
  if (type === "skills") return [["版本", escapeHtml(row.version)], ["运行时", escapeHtml(row.runtime)], ["说明", escapeHtml(row.description || "暂无说明")], ["能力", tags(row.capabilities)], ["包文件", escapeHtml(row.package_file_id || "未绑定")], ...common];
  if (type === "credentials") return [["Provider", escapeHtml(row.provider)], ["Secret Ref", escapeHtml(row.secret_ref || "安全引用")], ["指纹", escapeHtml(row.secret_fingerprint || "未生成")], ...common];
  if (type === "modelProviders") return [["Provider", escapeHtml(row.provider)], ["Credential", credentialName(row.credential_ref_id)], ["Base URL", escapeHtml(row.base_url || "默认")], ["模型", tags(row.models)], ...common];
  const versions = state.workflowVersions[row.id] || [];
  return [["项目", projectName(row.project_id)], ["说明", escapeHtml(row.description || "暂无说明")], ["当前版本", escapeHtml(row.active_version_id || "未激活")], ["版本数", String(versions.length)], ["节点总数", String(workflowNodeCount(row.id))], ["运行次数", String(workflowRunsFor(row.id).length)], ...common];
}

function relationshipControls(type, row) {
  if (state.role === "Viewer") return `<div class="permission-denied"><strong>无写入权限</strong><span>查看者可以查看关系，但不能修改绑定。</span></div>${relationshipList(type, row)}`;
  if (type === "projects") {
    const availableAssets = state.assets.filter((asset) => !(row.asset_ids || []).includes(asset.id));
    const availableEnvironments = state.environments.filter((env) => env.project_id === row.id && !(row.environment_ids || []).includes(env.id));
    const availableRepositories = repositoryBindingOptions(row);
    return `
      <form class="inline-form" data-action="link-project-asset" data-id="${row.id}">
        <label>绑定资产<select name="asset_id">${options(availableAssets, "没有可绑定资产")}</select></label>
        <button class="ghost-button small" type="submit">绑定</button>
      </form>
      <form class="inline-form" data-action="link-project-environment" data-id="${row.id}">
        <label>绑定环境<select name="environment_id">${options(availableEnvironments, "没有可绑定环境")}</select></label>
        <button class="ghost-button small" type="submit">绑定</button>
      </form>
      <form class="inline-form" data-action="link-project-repository" data-id="${row.id}">
        <label>绑定 GitLab 仓库<select name="repository_binding">${availableRepositories}</select></label>
        <button class="ghost-button small" type="submit">绑定</button>
      </form>
      <h4>已绑定资产</h4>${linkedList(row.asset_ids || [], "assets", "unlink-project-asset", row.id)}
      <h4>已绑定环境</h4>${linkedList(row.environment_ids || [], "environments", "unlink-project-environment", row.id)}
      <h4>已绑定仓库</h4>${repositoryBindingList(row)}
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
  if (type === "agents") return `<h4>关联 Skill</h4>${linkedNameList(row.skill_ids || [], "skills")}<h4>模型供应商</h4>${listItems([modelProviderName(row.model_provider_id)])}<h4>能力</h4>${listItems((row.capabilities || []).map(escapeHtml))}`;
  if (type === "gitlabProfiles") return `<h4>仓库选择</h4>${repositoryList(row.id)}<h4>引用项目</h4>${listItems(state.projects.filter((project) => (project.repository_bindings || []).some((binding) => binding.profile_id === row.id)).map((project) => escapeHtml(project.name)))}`;
  if (type === "vcsOperations") return `<h4>操作结果</h4>${jsonBlock(row.result || {})}<h4>Profile</h4>${listItems([gitlabProfileName(row.profile_id)])}`;
  if (type === "vcsWebhooks") return `<h4>脱敏 Payload</h4>${jsonBlock(sanitizeWebhookEvent(row).payload || {})}<h4>Profile</h4>${listItems([gitlabProfileName(row.profile_id)])}`;
  if (type === "files") return fileActionPanel(row);
  if (type === "testCases") return `<h4>步骤</h4>${listItems((row.steps || []).map((step) => escapeHtml(step.name || step.expected || JSON.stringify(step))))}<h4>所属套件</h4>${listItems(state.testSuites.filter((suite) => suite.case_ids?.includes(row.id)).map((suite) => escapeHtml(suite.name)))}`;
  if (type === "testSuites") return `<h4>用例清单</h4>${linkedNameList(row.case_ids || [], "testCases")}<h4>运行记录</h4>${listItems(state.testRuns.filter((run) => run.suite_id === row.id).map((run) => `运行 ${escapeHtml(run.id)} · ${statusPill(run.status)}`))}`;
  if (type === "testRuns") return `<h4>结果摘要</h4>${listItems((row.results || []).map((result) => `${testCaseName(result.case_id)} · ${statusPill(result.status || "pending")}`))}<h4>关联报告</h4>${listItems(state.reports.filter((report) => report.test_run_id === row.id).map((report) => escapeHtml(report.title)))}`;
  if (type === "reports") return `<h4>文件</h4>${linkedNameList(row.file_ids || [], "files")}<h4>质量门禁</h4>${listItems(state.qualityGates.filter((gate) => gate.last_report_id === row.id).map((gate) => `${escapeHtml(gate.name)} · ${statusPill(gate.status)}`))}`;
  if (type === "qualityGates") return `<h4>条件</h4>${jsonBlock(row.conditions || [])}<h4>最近报告</h4>${listItems([reportName(row.last_report_id)])}`;
  if (type === "skills") return `<h4>能力标签</h4>${listItems((row.capabilities || []).map(escapeHtml))}<h4>引用智能体</h4>${listItems(state.agents.filter((agent) => agent.skill_ids?.includes(row.id)).map((agent) => escapeHtml(agent.name)))}`;
  if (type === "credentials") return `<h4>使用此 Key 的供应商</h4>${listItems(state.modelProviders.filter((provider) => provider.credential_ref_id === row.id).map((provider) => escapeHtml(provider.name)))}`;
  if (type === "modelProviders") return `<h4>可用模型</h4>${listItems((row.models || []).map(escapeHtml))}<h4>引用智能体</h4>${listItems(state.agents.filter((agent) => agent.model_provider_id === row.id).map((agent) => escapeHtml(agent.name)))}`;
  if (type === "workflows") return workflowVersionPanel(row);
  return relationshipList(type, row);
}

function relationshipList(type, row) {
  if (type === "projects") return listItems([...(row.environment_ids || []).map(projectEnvLabel), ...(row.asset_ids || []).map(assetLabel), ...(row.repository_bindings || []).map((binding) => `仓库 ${repositoryName(binding.profile_id, binding.repository_id)}`)]);
  if (type === "assets") return listItems([row.parent_id ? `安装于 ${assetLabel(row.parent_id)}` : "无父级资产", ...state.assets.filter((asset) => asset.parent_id === row.id).map((asset) => `包含 ${escapeHtml(asset.name)}`)]);
  if (type === "environments") return listItems([...(row.member_ids || []).map((id) => `成员 ${nameFor("users", id)}`), ...(row.asset_ids || []).map((id) => `资产 ${assetLabel(id)}`), ...(row.endpoints || []).map((e) => `端点 ${escapeHtml(e.name)}: ${escapeHtml(e.url)}`)]);
  if (type === "gitlabProfiles") return repositoryList(row.id);
  if (type === "vcsOperations") return listItems([gitlabProfileName(row.profile_id), repositoryName(row.profile_id, row.repository_id), escapeHtml(row.external_id || "无外部 ID")]);
  if (type === "vcsWebhooks") return listItems([gitlabProfileName(row.profile_id), repositoryName(row.profile_id, row.repository_id), escapeHtml(row.event_type)]);
  if (type === "files") return fileActionPanel(row);
  if (type === "testCases") return listItems((row.steps || []).map((step) => escapeHtml(JSON.stringify(step))));
  if (type === "testSuites") return linkedNameList(row.case_ids || [], "testCases");
  if (type === "testRuns") return listItems((row.results || []).map((result) => `${testCaseName(result.case_id)} · ${statusPill(result.status || "pending")}`));
  if (type === "reports") return linkedNameList(row.file_ids || [], "files");
  if (type === "qualityGates") return listItems((row.conditions || []).map((condition) => escapeHtml(JSON.stringify(condition))));
  if (type === "agents") return listItems([...(row.skill_ids || []).map((id) => `Skill ${skillName(id)}`), row.model_provider_id ? `模型 ${modelProviderName(row.model_provider_id)}` : "未绑定模型供应商"]);
  if (type === "skills") return listItems(state.agents.filter((agent) => agent.skill_ids?.includes(row.id)).map((agent) => `智能体 ${escapeHtml(agent.name)}`));
  if (type === "credentials") return listItems(state.modelProviders.filter((provider) => provider.credential_ref_id === row.id).map((provider) => `供应商 ${escapeHtml(provider.name)}`));
  if (type === "modelProviders") return listItems(state.agents.filter((agent) => agent.model_provider_id === row.id).map((agent) => `智能体 ${escapeHtml(agent.name)}`));
  if (type === "workflows") return `${workflowVersionList(row.id)}${workflowRunPanel(row)}`;
  return listItems(state.projects.filter((project) => project.member_ids?.includes(row.id) || project.owner_id === row.id).map((project) => `项目 ${escapeHtml(project.key)}`));
}

const workflowPalette = [
  { type: "trigger", group: "触发器", icon: "TR", name: "触发器", help: "手动、GitLab Webhook 或测试报告完成触发" },
  { type: "agent_task", group: "智能体任务", icon: "AI", name: "智能体任务", help: "绑定智能体、Skill 与模型供应商执行运维动作" },
  { type: "approval", group: "人工控制", icon: "OK", name: "人工确认", help: "发布准入、回滚确认或人工复核" },
  { type: "result", group: "结果/通知", icon: "RS", name: "结果/通知", help: "沉淀执行结果、报告备注和审计映射" },
];

function openWorkflowBuilder(workflowId, options = {}) {
  const workflow = state.workflows.find((row) => row.id === workflowId);
  if (!workflow) return showError("未找到流程定义。");
  state.route = "workflows";
  state.workflowBuilder = {
    workflowId,
    selectedNodeId: "",
    selectedEdgeKey: "",
    validation: null,
    preview: Boolean(options.preview),
    draft: workflowDraftFromVersion(workflow),
  };
  state.workflowBuilder.validation = validateWorkflowDraft(state.workflowBuilder.draft);
  render();
}

function workflowDraftFromVersion(workflow) {
  const versions = state.workflowVersions[workflow.id] || [];
  const source = versions.find((version) => version.id === workflow.active_version_id) || versions.at(-1);
  const nextVersion = String(Math.max(0, ...versions.map((version) => Number(version.version) || 0)) + 1);
  const baseNodes = source?.nodes?.length ? source.nodes : [
    { id: "trigger", type: "trigger", name: "发布触发", trigger_mode: "manual", project_id: workflow.project_id || "" },
    { id: "agent-task", type: "agent_task", name: "发布前巡检", agent_id: state.agents[0]?.id || "", skill_id: state.agents[0]?.skill_ids?.[0] || "", model_provider_id: state.agents[0]?.model_provider_id || "", input: "读取项目、环境和最近测试报告，输出发布风险结论。", timeout_seconds: 900, failure_strategy: "stop" },
    { id: "approval", type: "approval", name: "人工确认", approval_role: "Operator", instructions: "确认巡检结果后继续发布。", timeout_strategy: "转人工复核" },
  ];
  const seenIds = new Set();
  const idMap = new Map();
  const nodes = baseNodes.map((node, index) => ({
    ...node,
    id: safeWorkflowNodeId(node.id, index, seenIds, idMap),
    type: safeWorkflowNodeType(node.type),
    name: node.name || defaultWorkflowNodeName(safeWorkflowNodeType(node.type), index + 1),
    x: Number(node.x ?? 48 + index * 200),
    y: Number(node.y ?? 120 + (index % 2) * 24),
  }));
  const edges = (source?.edges?.length ? source.edges : nodes.slice(0, -1).map((node, index) => ({ from_node_id: node.id, to_node_id: nodes[index + 1].id })))
    .map((edge) => ({ from_node_id: idMap.get(String(edge.from_node_id)) || edge.from_node_id, to_node_id: idMap.get(String(edge.to_node_id)) || edge.to_node_id }))
    .filter((edge) => nodes.some((node) => node.id === edge.from_node_id) && nodes.some((node) => node.id === edge.to_node_id));
  return { workflow_id: workflow.id, base_version_id: source?.id || "", version: nextVersion, status: "draft", nodes, edges };
}

function renderWorkflowBuilder() {
  const builder = state.workflowBuilder;
  const workflow = state.workflows.find((row) => row.id === builder.workflowId);
  if (!builder || !workflow) {
    state.workflowBuilder = null;
    renderResource("workflows");
    return;
  }
  const validation = builder.validation || validateWorkflowDraft(builder.draft);
  const selectedNode = builder.draft.nodes.find((node) => node.id === builder.selectedNodeId);
  content.innerHTML = `
    <section class="workflow-builder">
      <header class="builder-topbar">
        <div>
          <p class="eyebrow">运维流程 Builder</p>
          <h1>${escapeHtml(workflow.name)}</h1>
          <p class="muted">${projectName(workflow.project_id)} · 草稿版本 ${escapeHtml(builder.draft.version)} · ${builder.draft.nodes.length} 节点 / ${builder.draft.edges.length} 边</p>
        </div>
        <div class="action-row">
          <button class="ghost-button" data-builder-action="validate">校验</button>
          <button class="ghost-button" data-builder-action="preview" ${validation.errors.length ? "disabled title=\"请先修复 Error\"" : ""}>运行预览</button>
          <button class="primary-button" data-builder-action="save">保存版本</button>
          <button class="ghost-button" data-builder-action="exit">退出画布</button>
        </div>
      </header>
      <div class="builder-shell">
        <aside class="builder-palette">
          <h2>节点 Palette</h2>
          ${workflowPaletteGroups()}
          <form class="edge-form" data-builder-action="add-edge">
            <h3>连接节点</h3>
            <label>起点<select name="from_node_id">${workflowNodeOptions(builder.draft.nodes, "")}</select></label>
            <label>终点<select name="to_node_id">${workflowNodeOptions(builder.draft.nodes, "")}</select></label>
            <button class="ghost-button small" type="submit">创建连线</button>
          </form>
        </aside>
        <main class="builder-stage">
          <div class="builder-stage-head">
            <div class="segmented-control"><button class="active">画布</button><button>列表</button></div>
            <div class="action-row"><button class="ghost-button small" data-builder-action="fit">适配画布</button><span class="pill">${validation.errors.length ? `${validation.errors.length} Error` : validation.warnings.length ? `${validation.warnings.length} Warning` : "校验通过"}</span></div>
          </div>
          <div class="workflow-canvas" data-builder-dropzone>
            <svg class="workflow-edges" viewBox="0 0 920 520" preserveAspectRatio="none" aria-hidden="true">${workflowEdgesSvg(builder.draft)}</svg>
            ${builder.draft.nodes.map((node) => workflowNodeCard(node, validation)).join("")}
          </div>
          <div class="workflow-list-fallback">
            <h3>移动端节点列表</h3>
            ${builder.draft.nodes.map((node, index) => workflowNodeListItem(node, index, validation)).join("")}
          </div>
        </main>
        <aside class="builder-inspector">
          ${selectedNode ? workflowNodeInspector(selectedNode, validation) : workflowSummaryInspector(workflow, validation)}
        </aside>
      </div>
      ${builder.preview ? workflowRunPreview(builder.draft, validation) : ""}
    </section>
  `;
  bindWorkflowBuilder();
}

function workflowPaletteGroups() {
  const groups = [...new Set(workflowPalette.map((item) => item.group))];
  return groups.map((group) => `
    <div class="palette-group">
      <h3>${group}</h3>
      ${workflowPalette.filter((item) => item.group === group).map((item) => `
        <button class="palette-item" draggable="true" data-builder-action="add-node" data-node-type="${item.type}">
          <span>${item.icon}</span><strong>${item.name}</strong><small>${item.help}</small>
        </button>
      `).join("")}
    </div>
  `).join("");
}

function workflowNodeCard(node, validation) {
  const tone = workflowNodeValidationTone(node.id, validation);
  const summary = workflowNodeSummary(node);
  return `<button class="workflow-node ${tone}" draggable="true" data-builder-action="select-node" data-node-id="${escapeAttr(node.id)}" style="left:${Number(node.x || 0)}px;top:${Number(node.y || 0)}px">
    <span class="node-type">${workflowNodeTypeLabel(node.type)}</span>
    <strong>${escapeHtml(node.name)}</strong>
    <small>${summary}</small>
  </button>`;
}

function workflowNodeListItem(node, index, validation) {
  const tone = workflowNodeValidationTone(node.id, validation);
  return `<button class="workflow-list-item ${tone}" data-builder-action="select-node" data-node-id="${escapeAttr(node.id)}">
    <span>${index + 1}</span><div><strong>${escapeHtml(node.name)}</strong><small>${workflowNodeTypeLabel(node.type)} · ${workflowNodeSummary(node)}</small></div>
  </button>`;
}

function workflowEdgesSvg(draft) {
  const byId = Object.fromEntries(draft.nodes.map((node) => [node.id, node]));
  return draft.edges.map((edge) => {
    const from = byId[edge.from_node_id];
    const to = byId[edge.to_node_id];
    if (!from || !to) return "";
    const x1 = Number(from.x || 0) + 170;
    const y1 = Number(from.y || 0) + 44;
    const x2 = Number(to.x || 0);
    const y2 = Number(to.y || 0) + 44;
    const mid = Math.max(x1 + 40, (x1 + x2) / 2);
    return `<path d="M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}" /><circle cx="${x2}" cy="${y2}" r="4" />`;
  }).join("");
}

function workflowNodeInspector(node, validation) {
  const nodeErrors = validation.errors.filter((item) => item.nodeId === node.id);
  const nodeWarnings = validation.warnings.filter((item) => item.nodeId === node.id);
  return `
    <h2>节点详情</h2>
    <form class="node-config-form" data-builder-action="update-node" data-node-id="${escapeAttr(node.id)}">
      <label>节点名<input name="name" value="${escapeAttr(node.name)}" required /></label>
      ${workflowNodeFields(node)}
      <div class="action-row">
        <button class="primary-button" type="submit">保存节点配置</button>
        <button class="ghost-button danger" type="button" data-builder-action="delete-node" data-node-id="${escapeAttr(node.id)}">删除节点</button>
      </div>
    </form>
    ${validationList("Error", nodeErrors, "bad")}
    ${validationList("Warning", nodeWarnings, "warn")}
  `;
}

function workflowNodeFields(node) {
  if (node.type === "trigger") return `
    <label>触发方式<select name="trigger_mode">${selectedOptions(["manual", "gitlab_webhook", "test_report_completed"], node.trigger_mode || "manual")}</select></label>
    <label>关联项目<select name="project_id"><option value="">平台级</option>${state.projects.map((project) => `<option value="${project.id}" ${node.project_id === project.id ? "selected" : ""}>${escapeHtml(project.key)} · ${escapeHtml(project.name)}</option>`).join("")}</select></label>
  `;
  if (node.type === "agent_task") return `
    <label>智能体<select name="agent_id">${workflowAgentOptions(node.agent_id)}</select></label>
    <label>Skill<select name="skill_id">${workflowSkillOptions(node.agent_id, node.skill_id)}</select></label>
    <label>模型供应商<select name="model_provider_id">${workflowProviderOptions(node.agent_id, node.model_provider_id)}</select></label>
    <label>输入说明<textarea name="input">${escapeHtml(node.input || "")}</textarea></label>
    <label>超时秒数<input name="timeout_seconds" type="number" min="30" value="${escapeAttr(node.timeout_seconds || 900)}" /></label>
    <label>失败策略<select name="failure_strategy">${selectedOptions(["stop", "continue_mark", "manual_review"], node.failure_strategy || "")}</select></label>
  `;
  if (node.type === "approval") return `
    <label>审批角色<select name="approval_role">${selectedOptions(["Admin", "Operator", "Viewer"], node.approval_role || "Operator")}</select></label>
    <label>确认说明<textarea name="instructions">${escapeHtml(node.instructions || "")}</textarea></label>
    <label>超时策略<input name="timeout_strategy" value="${escapeAttr(node.timeout_strategy || "转人工复核")}" /></label>
  `;
  return `
    <label>结果名<input name="result_name" value="${escapeAttr(node.result_name || node.name)}" /></label>
    <label>状态映射<input name="status_mapping" value="${escapeAttr(node.status_mapping || "passed=通过,failed=阻断")}" /></label>
    <label>审计备注<textarea name="audit_note">${escapeHtml(node.audit_note || "")}</textarea></label>
  `;
}

function workflowSummaryInspector(workflow, validation) {
  return `
    <h2>流程摘要</h2>
    <dl class="kv">
      <dt>流程</dt><dd>${escapeHtml(workflow.name)}</dd>
      <dt>项目</dt><dd>${projectName(workflow.project_id)}</dd>
      <dt>校验</dt><dd>${validation.errors.length ? statusPill("failed") : validation.warnings.length ? statusPill("warning") : statusPill("passed")}</dd>
    </dl>
    ${validationList("Error", validation.errors, "bad")}
    ${validationList("Warning", validation.warnings, "warn")}
  `;
}

function workflowRunPreview(draft, validation) {
  if (validation.errors.length) return "";
  const ordered = workflowExecutionOrder(draft);
  return `<section class="run-preview panel">
    <div class="detail-heading"><div><p class="eyebrow">运行预览</p><h2>只读执行计划</h2></div>${validation.warnings.length ? statusPill("warning") : statusPill("passed")}</div>
    <ol class="timeline">${ordered.map((node, index) => `<li><span>${index + 1}</span><div><strong>${escapeHtml(node.name)}</strong><small>${workflowNodeTypeLabel(node.type)} · ${workflowPreviewCopy(node)}</small></div></li>`).join("")}</ol>
  </section>`;
}

function bindWorkflowBuilder() {
  const builder = state.workflowBuilder;
  content.querySelectorAll("[data-builder-action]").forEach((node) => {
    if (node.tagName === "FORM") {
      node.addEventListener("submit", async (event) => {
        event.preventDefault();
        await handleWorkflowBuilderAction(node.dataset.builderAction, node, new FormData(node)).catch((error) => showError(error.message));
      });
      return;
    }
    node.addEventListener("click", async () => {
      await handleWorkflowBuilderAction(node.dataset.builderAction, node, null).catch((error) => showError(error.message));
    });
    if (node.dataset.builderAction === "add-node") {
      node.addEventListener("dragstart", (event) => event.dataTransfer.setData("text/plain", node.dataset.nodeType));
    }
    if (node.dataset.builderAction === "select-node") {
      node.addEventListener("dragstart", (event) => event.dataTransfer.setData("application/x-node-id", node.dataset.nodeId));
    }
  });
  const dropzone = content.querySelector("[data-builder-dropzone]");
  if (dropzone) {
    dropzone.addEventListener("dragover", (event) => event.preventDefault());
    dropzone.addEventListener("drop", (event) => {
      event.preventDefault();
      const rect = dropzone.getBoundingClientRect();
      const nodeId = event.dataTransfer.getData("application/x-node-id");
      const type = event.dataTransfer.getData("text/plain");
      if (nodeId) {
        const node = builder.draft.nodes.find((item) => item.id === nodeId);
        if (node) {
          node.x = Math.max(16, Math.round(event.clientX - rect.left - 85));
          node.y = Math.max(16, Math.round(event.clientY - rect.top - 40));
        }
      } else if (type) {
        addWorkflowNode(type, Math.max(16, Math.round(event.clientX - rect.left)), Math.max(16, Math.round(event.clientY - rect.top)));
      }
      refreshWorkflowBuilder();
    });
  }
}

async function handleWorkflowBuilderAction(action, node, form) {
  if (action === "exit") {
    const workflowId = state.workflowBuilder.workflowId;
    state.workflowBuilder = null;
    state.detail = { type: "workflows", id: workflowId };
    renderResource("workflows");
    return;
  }
  if (action === "fit") {
    fitWorkflowDraft();
    refreshWorkflowBuilder();
    return;
  }
  if (action === "validate") {
    state.workflowBuilder.validation = validateWorkflowDraft(state.workflowBuilder.draft);
    state.workflowBuilder.preview = false;
    refreshWorkflowBuilder("校验已完成。");
    return;
  }
  if (action === "preview") {
    state.workflowBuilder.validation = validateWorkflowDraft(state.workflowBuilder.draft);
    if (state.workflowBuilder.validation.errors.length) return showError("存在 Error，请先修复后再预览。");
    state.workflowBuilder.preview = true;
    refreshWorkflowBuilder();
    return;
  }
  if (action === "save") return saveWorkflowBuilderVersion();
  if (action === "add-node") {
    addWorkflowNode(node.dataset.nodeType);
    refreshWorkflowBuilder();
    return;
  }
  if (action === "select-node") {
    state.workflowBuilder.selectedNodeId = node.dataset.nodeId;
    state.workflowBuilder.selectedEdgeKey = "";
    state.workflowBuilder.preview = false;
    refreshWorkflowBuilder();
    return;
  }
  if (action === "delete-node") {
    deleteWorkflowNode(node.dataset.nodeId);
    refreshWorkflowBuilder();
    return;
  }
  if (action === "update-node") {
    updateWorkflowNode(node.dataset.nodeId, form);
    refreshWorkflowBuilder("节点配置已更新。");
    return;
  }
  if (action === "add-edge") {
    addWorkflowEdge(form.get("from_node_id"), form.get("to_node_id"));
    refreshWorkflowBuilder();
  }
}

function refreshWorkflowBuilder(message = "") {
  state.workflowBuilder.validation = validateWorkflowDraft(state.workflowBuilder.draft);
  renderWorkflowBuilder();
  if (message) toast(message);
}

function addWorkflowNode(type, x = 80, y = 120) {
  const draft = state.workflowBuilder.draft;
  type = safeWorkflowNodeType(type);
  const count = draft.nodes.filter((node) => node.type === type).length + 1;
  const id = safeWorkflowNodeId(`${type.replace("_", "-")}-${Date.now().toString(36)}-${count}`, draft.nodes.length, new Set(draft.nodes.map((node) => node.id)), new Map());
  const node = { id, type, name: defaultWorkflowNodeName(type, count), x, y };
  if (type === "trigger") Object.assign(node, { trigger_mode: "manual", project_id: state.workflows.find((workflow) => workflow.id === draft.workflow_id)?.project_id || "" });
  if (type === "agent_task") Object.assign(node, { agent_id: state.agents[0]?.id || "", skill_id: state.agents[0]?.skill_ids?.[0] || "", model_provider_id: state.agents[0]?.model_provider_id || "", input: "", timeout_seconds: 900, failure_strategy: "stop" });
  if (type === "approval") Object.assign(node, { approval_role: "Operator", instructions: "", timeout_strategy: "转人工复核" });
  if (type === "result") Object.assign(node, { result_name: node.name, status_mapping: "passed=通过,failed=阻断", audit_note: "" });
  draft.nodes.push(node);
  state.workflowBuilder.selectedNodeId = id;
}

function updateWorkflowNode(nodeId, form) {
  const node = state.workflowBuilder.draft.nodes.find((item) => item.id === nodeId);
  if (!node) return;
  for (const [key, value] of form.entries()) {
    node[key] = key === "timeout_seconds" ? Number(value || 0) : value;
  }
  if (node.type === "agent_task") {
    const agent = state.agents.find((item) => item.id === node.agent_id);
    if (!node.skill_id && agent?.skill_ids?.length) node.skill_id = agent.skill_ids[0];
    if (!node.model_provider_id && agent?.model_provider_id) node.model_provider_id = agent.model_provider_id;
  }
}

function deleteWorkflowNode(nodeId) {
  const draft = state.workflowBuilder.draft;
  const node = draft.nodes.find((item) => item.id === nodeId);
  if (!node) return;
  if (node.type === "trigger" && !confirm("确认删除触发器？流程需要重新添加一个触发器后才能保存。")) return;
  draft.nodes = draft.nodes.filter((item) => item.id !== nodeId);
  draft.edges = draft.edges.filter((edge) => edge.from_node_id !== nodeId && edge.to_node_id !== nodeId);
  state.workflowBuilder.selectedNodeId = "";
}

function addWorkflowEdge(fromNodeId, toNodeId) {
  const draft = state.workflowBuilder.draft;
  if (!fromNodeId || !toNodeId) return showError("请选择连线起点和终点。");
  if (fromNodeId === toNodeId) return showError("不支持节点自连。");
  if (draft.edges.some((edge) => edge.from_node_id === fromNodeId && edge.to_node_id === toNodeId)) return showError("重复连线已存在。");
  draft.edges.push({ from_node_id: fromNodeId, to_node_id: toNodeId });
}

async function saveWorkflowBuilderVersion() {
  const builder = state.workflowBuilder;
  builder.validation = validateWorkflowDraft(builder.draft);
  if (builder.validation.errors.length) {
    refreshWorkflowBuilder();
    return showError("存在 Error，请修复后再保存版本。");
  }
  const payload = workflowVersionPayload(builder.draft);
  if (state.apiOnline) {
    const created = await apiRequest("POST", `/v1/workflows/${builder.workflowId}/versions`, payload);
    state.workflowVersions[builder.workflowId] = [...(state.workflowVersions[builder.workflowId] || []).filter((version) => version.id !== created.id), created];
  } else {
    const item = { ...payload, id: `wfv_local_${Date.now()}`, workflow_id: builder.workflowId, created_at: new Date().toISOString(), updated_at: new Date().toISOString() };
    state.workflowVersions[builder.workflowId] = [...(state.workflowVersions[builder.workflowId] || []), item];
    const workflow = state.workflows.find((row) => row.id === builder.workflowId);
    if (workflow && !workflow.active_version_id) workflow.active_version_id = item.id;
  }
  state.workflowBuilder = null;
  state.detail = { type: "workflows", id: builder.workflowId };
  if (state.apiOnline) await loadData();
  else render();
  toast("流程版本已保存。");
}

function workflowVersionPayload(draft) {
  const seenIds = new Set();
  const idMap = new Map();
  const nodes = draft.nodes.map((node, index) => ({ ...node, id: safeWorkflowNodeId(node.id, index, seenIds, idMap), type: safeWorkflowNodeType(node.type) }));
  return {
    version: String(draft.version || "1"),
    status: draft.status || "draft",
    nodes: nodes.map((node) => Object.fromEntries(Object.entries(node).filter(([key, value]) => !["x", "y"].includes(key) && value !== "" && value !== undefined))),
    edges: draft.edges.map((edge) => ({ from_node_id: idMap.get(String(edge.from_node_id)) || edge.from_node_id, to_node_id: idMap.get(String(edge.to_node_id)) || edge.to_node_id }))
      .filter((edge) => nodes.some((node) => node.id === edge.from_node_id) && nodes.some((node) => node.id === edge.to_node_id)),
  };
}

function validateWorkflowDraft(draft = { nodes: [], edges: [] }) {
  const errors = [];
  const warnings = [];
  const nodes = draft.nodes || [];
  const edges = draft.edges || [];
  const nodeIds = new Set(nodes.map((node) => node.id));
  const triggers = nodes.filter((node) => node.type === "trigger");
  if (!triggers.length) errors.push({ message: "流程必须包含 1 个触发器。" });
  if (triggers.length > 1) errors.push({ message: "流程只能包含 1 个触发器。", nodeId: triggers[1]?.id });
  for (const edge of edges) {
    if (!nodeIds.has(edge.from_node_id) || !nodeIds.has(edge.to_node_id)) errors.push({ message: "存在引用不存在节点的边。" });
  }
  for (const node of nodes) {
    const inbound = edges.some((edge) => edge.to_node_id === node.id);
    const outbound = edges.some((edge) => edge.from_node_id === node.id);
    if (node.type !== "trigger" && !inbound) errors.push({ message: `${node.name} 是孤立节点，缺少入边。`, nodeId: node.id });
    if (nodes.length > 1 && !outbound && !["approval", "result"].includes(node.type)) warnings.push({ message: `${node.name} 未连接到终点。`, nodeId: node.id });
    if (node.type === "agent_task") {
      const agent = state.agents.find((item) => item.id === node.agent_id);
      if (!node.agent_id) errors.push({ message: `${node.name} 缺少智能体。`, nodeId: node.id });
      if (node.skill_id && agent && !(agent.skill_ids || []).includes(node.skill_id)) errors.push({ message: `${node.name} 的 Skill 不属于所选智能体。`, nodeId: node.id });
      if (node.model_provider_id && agent && agent.model_provider_id && node.model_provider_id !== agent.model_provider_id) errors.push({ message: `${node.name} 的模型供应商不匹配智能体。`, nodeId: node.id });
      if (!node.input) warnings.push({ message: `${node.name} 未填写输入说明。`, nodeId: node.id });
      if (!node.failure_strategy) warnings.push({ message: `${node.name} 未配置失败策略。`, nodeId: node.id });
    }
  }
  if (!nodes.some((node) => node.type === "approval")) warnings.push({ message: "流程缺少人工确认节点。" });
  if (hasWorkflowCycle(nodes, edges)) errors.push({ message: "流程存在环，请调整连线。" });
  if (triggers[0] && workflowExecutionOrder(draft).length < Math.min(nodes.length, 1)) errors.push({ message: "触发器无法到达任何节点。", nodeId: triggers[0].id });
  return { errors, warnings };
}

function hasWorkflowCycle(nodes, edges) {
  const visiting = new Set();
  const visited = new Set();
  const next = (id) => edges.filter((edge) => edge.from_node_id === id).map((edge) => edge.to_node_id);
  function walk(id) {
    if (visiting.has(id)) return true;
    if (visited.has(id)) return false;
    visiting.add(id);
    for (const target of next(id)) if (walk(target)) return true;
    visiting.delete(id);
    visited.add(id);
    return false;
  }
  return nodes.some((node) => walk(node.id));
}

function workflowExecutionOrder(draft) {
  const byId = Object.fromEntries((draft.nodes || []).map((node) => [node.id, node]));
  const start = (draft.nodes || []).find((node) => node.type === "trigger") || draft.nodes?.[0];
  if (!start) return [];
  const seen = new Set();
  const ordered = [];
  let current = start.id;
  while (current && byId[current] && !seen.has(current)) {
    seen.add(current);
    ordered.push(byId[current]);
    current = (draft.edges || []).find((edge) => edge.from_node_id === current)?.to_node_id;
  }
  return ordered;
}

function validationList(title, items, tone) {
  if (!items.length) return `<div class="empty-state compact">暂无${title}。</div>`;
  return `<h3>${title}</h3><ul class="validation-list">${items.map((item) => `<li><button data-builder-action="select-node" data-node-id="${escapeAttr(item.nodeId || "")}" ${item.nodeId ? "" : "disabled"}><span class="pill ${tone}">${title}</span>${escapeHtml(item.message)}</button></li>`).join("")}</ul>`;
}

function workflowNodeValidationTone(nodeId, validation) {
  if (validation.errors.some((item) => item.nodeId === nodeId)) return "bad";
  if (validation.warnings.some((item) => item.nodeId === nodeId)) return "warn";
  return "ok";
}

function workflowNodeSummary(node) {
  if (node.type === "trigger") return escapeHtml({ manual: "手动触发", gitlab_webhook: "GitLab Webhook", test_report_completed: "测试报告完成" }[node.trigger_mode] || "未配置触发方式");
  if (node.type === "agent_task") return `${agentName(node.agent_id)} · ${skillName(node.skill_id)} · ${modelProviderName(node.model_provider_id)}`;
  if (node.type === "approval") return `${displayRole(node.approval_role || "Operator")} · ${escapeHtml(node.timeout_strategy || "未配置超时")}`;
  return escapeHtml(node.result_name || "输出执行结果");
}

function workflowPreviewCopy(node) {
  if (node.type === "trigger") return workflowNodeSummary(node);
  if (node.type === "agent_task") return `${workflowNodeSummary(node)} · 失败策略 ${escapeHtml(translateWorkflowFailure(node.failure_strategy))}`;
  if (node.type === "approval") return `${workflowNodeSummary(node)} · ${escapeHtml(node.instructions || "等待人工确认")}`;
  return escapeHtml(node.audit_note || node.status_mapping || "写入流程审计与报告备注");
}

function workflowNodeTypeLabel(type) {
  return { trigger: "触发器", agent_task: "智能体任务", approval: "人工确认", result: "结果/通知" }[safeWorkflowNodeType(type)] || "未知节点";
}

function defaultWorkflowNodeName(type, count) {
  return `${workflowNodeTypeLabel(type)} ${count}`;
}

function workflowAgentOptions(selected) {
  return `<option value="">请选择智能体</option>${state.agents.map((agent) => `<option value="${agent.id}" ${selected === agent.id ? "selected" : ""}>${escapeHtml(agent.name)}</option>`).join("")}`;
}

function workflowSkillOptions(agentId, selected) {
  const agent = state.agents.find((item) => item.id === agentId);
  const allowed = agent?.skill_ids?.length ? state.skills.filter((skill) => agent.skill_ids.includes(skill.id)) : state.skills;
  return `<option value="">请选择 Skill</option>${allowed.map((skill) => `<option value="${skill.id}" ${selected === skill.id ? "selected" : ""}>${escapeHtml(skill.name)} · ${escapeHtml(skill.version)}</option>`).join("")}`;
}

function workflowProviderOptions(agentId, selected) {
  const agent = state.agents.find((item) => item.id === agentId);
  const providers = agent?.model_provider_id ? state.modelProviders.filter((provider) => provider.id === agent.model_provider_id) : state.modelProviders;
  return `<option value="">请选择模型供应商</option>${providers.map((provider) => `<option value="${provider.id}" ${selected === provider.id ? "selected" : ""}>${escapeHtml(provider.name)}</option>`).join("")}`;
}

function workflowNodeOptions(nodes, selected) {
  return `<option value="">请选择节点</option>${nodes.map((node) => `<option value="${escapeAttr(node.id)}" ${selected === node.id ? "selected" : ""}>${escapeHtml(node.name)}</option>`).join("")}`;
}

function agentName(id) {
  const agent = state.agents.find((item) => item.id === id);
  return escapeHtml(agent ? agent.name : id || "未绑定智能体");
}

function translateWorkflowFailure(value) {
  return { stop: "停止", continue_mark: "继续并标记", manual_review: "转人工" }[value] || "未配置";
}

function fitWorkflowDraft() {
  state.workflowBuilder.draft.nodes.forEach((node, index) => {
    node.x = 48 + (index % 4) * 200;
    node.y = 96 + Math.floor(index / 4) * 130;
  });
}

function safeWorkflowNodeType(type) {
  return ["trigger", "agent_task", "approval", "result"].includes(type) ? type : "result";
}

function safeWorkflowNodeId(value, index, seenIds, idMap) {
  const original = String(value || "");
  const base = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(original) ? original : `node-${index + 1}`;
  let candidate = base;
  let suffix = 2;
  while (seenIds.has(candidate)) {
    candidate = `${base}-${suffix}`;
    suffix += 1;
  }
  seenIds.add(candidate);
  idMap.set(original, candidate);
  return candidate;
}

function workflowVersionPanel(workflow) {
  const versions = state.workflowVersions[workflow.id] || [];
  const latest = String(versions.length + 1);
  const agentOptions = `<option value="">不绑定智能体</option>${state.agents.map((agent) => `<option value="${agent.id}">${escapeHtml(agent.name)}</option>`).join("")}`;
  const skillOptions = `<option value="">不绑定 Skill</option>${state.skills.map((skill) => `<option value="${skill.id}">${escapeHtml(skill.name)} · ${escapeHtml(skill.version)}</option>`).join("")}`;
  const providerOptions = `<option value="">使用智能体默认模型</option>${state.modelProviders.map((provider) => `<option value="${provider.id}">${escapeHtml(provider.name)}</option>`).join("")}`;
  return `
    <h4>流程版本</h4>${workflowVersionList(workflow.id)}
    <div class="action-row workflow-panel-actions">
      ${actionButton("link", "编辑画布", "primary-button", `detail-builder-${workflow.id}`, { actionName: "open-workflow-builder", id: workflow.id })}
      ${actionButton("link", "运行预览", "ghost-button", `detail-preview-${workflow.id}`, { actionName: "open-workflow-builder-preview", id: workflow.id })}
      ${actionButton("link", "创建运行", "ghost-button", `detail-create-run-${workflow.id}`, { actionName: "create-workflow-run", id: workflow.id })}
      ${actionButton("link", "创建并启动", "primary-button", `detail-create-start-run-${workflow.id}`, { actionName: "create-start-workflow-run", id: workflow.id })}
    </div>
    ${workflowRunPanel(workflow)}
    ${can("create") ? `<form class="form-grid" data-action="create-workflow-version" data-id="${workflow.id}">
      <label>版本号<input name="version" value="${latest}" required /></label>
      <label>状态<select name="status">${selectedOptions(["draft", "active", "deprecated"], "draft")}</select></label>
      <label>智能体<select name="agent_id">${agentOptions}</select></label>
      <label>Skill<select name="skill_id">${skillOptions}</select></label>
      <label class="full">模型供应商<select name="model_provider_id">${providerOptions}</select></label>
      <button class="primary-button full" type="submit">创建流程版本</button>
    </form>` : ""}
  `;
}

function workflowVersionList(workflowId) {
  const versions = state.workflowVersions[workflowId] || [];
  return versions.length ? `<ul class="link-list">${versions.map((version) => {
    const validation = validateWorkflowDraft(version);
    const validationStatus = validation.errors.length ? "failed" : validation.warnings.length ? "warning" : "passed";
    return `<li><span>版本 ${escapeHtml(version.version)} · ${statusPill(version.status)} · ${version.nodes?.length || 0} 节点 / ${version.edges?.length || 0} 边 · ${statusPill(validationStatus)}</span></li>`;
  }).join("")}</ul>` : `<div class="empty-state compact">暂无流程版本。</div>`;
}

function workflowRunPanel(workflow) {
  const runs = workflowRunsFor(workflow.id);
  const activeVersion = activeWorkflowVersion(workflow);
  const latestRun = runs[0];
  return `
    <section class="workflow-run-panel">
      <div class="detail-heading">
        <div>
          <p class="eyebrow">执行控制</p>
          <h4>运行实例</h4>
          <p class="muted">${activeVersion ? `激活版本 ${escapeHtml(activeVersion.version)} · ${activeVersion.nodes?.length || 0} 节点` : "当前流程未激活版本，无法创建运行。"}</p>
        </div>
        <span>${latestRun ? statusPill(latestRun.status) : statusPill("pending")}</span>
      </div>
      ${runs.length ? `<ul class="run-list">${runs.map((run) => workflowRunListItem(run, latestRun?.id === run.id)).join("")}</ul>` : `<div class="empty-state compact">暂无运行实例。创建运行后会从激活版本快照生成步骤。</div>`}
      ${latestRun ? workflowRunTimeline(latestRun) : ""}
    </section>
  `;
}

function workflowRunListItem(run, isLatest) {
  return `<li class="${isLatest ? "active" : ""}">
    <div>
      <strong>${escapeHtml(run.id)}</strong>
      <small>版本 ${escapeHtml(run.workflow_version_id)} · ${date(run.created_at)} · ${run.steps?.length || 0} 步骤</small>
    </div>
    <div class="action-row">
      ${statusPill(run.status)}
      ${workflowRunStartButton(run)}
    </div>
  </li>`;
}

function workflowRunStartButton(run) {
  if (run.status !== "created") return "";
  return actionButton("link", "启动运行", "ghost-button small", `start-run-${run.id}`, { actionName: "start-workflow-run", id: run.id });
}

function workflowRunTimeline(run) {
  const steps = [...(run.steps || [])].sort((a, b) => Number(a.sequence || 0) - Number(b.sequence || 0));
  return `
    <div class="run-timeline">
      <h4>步骤时间线</h4>
      ${steps.length ? steps.map((step) => workflowStepCard(run, step)).join("") : `<div class="empty-state compact">运行尚未生成步骤。</div>`}
    </div>
  `;
}

function workflowStepCard(run, step) {
  const gate = workflowStepGateState(run, step);
  return `<article class="run-step ${step.status}">
    <div class="step-main">
      <span class="step-index">${Number(step.sequence || 0)}</span>
      <div>
        <strong>${escapeHtml(step.name || step.node_id)}</strong>
        <small>${workflowStepTypeLabel(step.step_type)} · 节点 ${escapeHtml(step.node_id)} · ${statusPill(step.status)}</small>
      </div>
    </div>
    <p class="gate-copy ${gate.ready ? "ok" : "blocked"}">${gate.message}</p>
    ${workflowStepActions(run, step, gate)}
    ${workflowStepOutputBlock(step)}
    ${workflowStepErrorBlock(step)}
  </article>`;
}

function workflowStepOutputBlock(step) {
  const output = redactClientPayload(step.output || {});
  return output && Object.keys(output).length ? `<h5>输出</h5>${jsonBlock(output)}` : "";
}

function workflowStepErrorBlock(step) {
  const error = redactSensitiveString(step.error || "");
  return error ? `<h5>错误</h5><pre class="json-block error-block">${escapeHtml(error)}</pre>` : "";
}

function workflowStepActions(run, step, gate) {
  const statuses = workflowAllowedStepStatuses(run, step, gate);
  if (!statuses.length) return `<div class="muted">当前步骤暂无可执行流转。</div>`;
  return `<div class="action-row">${statuses.map((status) => actionButton("link", workflowStepActionLabel(step, status), `ghost-button small ${status === "failed" ? "danger" : ""}`, `step-${step.id}-${status}`, { actionName: "update-workflow-step", id: run.id, targetId: `${step.id}|${status}` })).join("")}</div>`;
}

function workflowAllowedStepStatuses(run, step, gate = workflowStepGateState(run, step)) {
  if (run.status !== "running" || step.step_type === "trigger" || !gate.ready) return [];
  if (["completed", "failed", "skipped"].includes(step.status)) return [];
  const statuses = step.status === "pending" ? ["running", "completed", "failed", "skipped"] : ["completed", "failed", "skipped"];
  return step.step_type === "manual" ? statuses.filter((status) => status !== "skipped") : statuses;
}

function workflowStepGateState(run, step) {
  const predecessorIds = step.predecessor_node_ids || [];
  if (!predecessorIds.length) return { ready: true, message: "无前置约束，可直接流转。" };
  const stepsByNode = Object.fromEntries((run.steps || []).map((candidate) => [candidate.node_id, candidate]));
  const waiting = [];
  for (const predecessorId of predecessorIds) {
    const predecessor = stepsByNode[predecessorId];
    if (!predecessor) {
      waiting.push(`${predecessorId} 缺失`);
      continue;
    }
    if (predecessor.step_type === "manual") {
      if (predecessor.status !== "completed") waiting.push(`${predecessor.name || predecessor.node_id} 需人工确认完成（当前${translateStatus(predecessor.status)}）`);
      continue;
    }
    if (!["completed", "skipped"].includes(predecessor.status)) waiting.push(`${predecessor.name || predecessor.node_id} 需完成或跳过（当前${translateStatus(predecessor.status)}）`);
  }
  return waiting.length ? { ready: false, message: `等待前置节点：${escapeHtml(waiting.join("；"))}` } : { ready: true, message: `前置约束已满足：${escapeHtml(predecessorIds.join("、"))}` };
}

function workflowStepActionLabel(step, status) {
  if (status === "running") return "标记执行中";
  if (status === "completed" && step.step_type === "manual") return "人工确认完成";
  if (status === "completed") return "标记完成";
  if (status === "failed" && step.step_type === "manual") return "人工拒绝";
  if (status === "failed") return "标记失败";
  return "跳过";
}

function workflowStepTypeLabel(type) {
  return { trigger: "触发器", agent: "智能体步骤", manual: "人工步骤", result: "结果步骤" }[type] || escapeHtml(type || "未知步骤");
}

function workflowRunsFor(workflowId) {
  return [...(state.workflowRuns || [])].filter((run) => run.workflow_id === workflowId).sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
}

function activeWorkflowVersion(workflow) {
  const versions = state.workflowVersions[workflow.id] || [];
  return versions.find((version) => version.id === workflow.active_version_id) || versions.find((version) => version.status === "active") || versions.at(-1);
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
  const skillOptions = state.skills.map((skill) => `<option value="${skill.id}" ${row.skill_ids?.includes(skill.id) ? "selected" : ""}>${escapeHtml(skill.name)} · ${escapeHtml(skill.version)}</option>`).join("");
  const modelProviderOptions = `<option value="">暂不绑定</option>${state.modelProviders.map((provider) => `<option value="${provider.id}" ${row.model_provider_id === provider.id || row.credential_ref_id === provider.id ? "selected" : ""}>${escapeHtml(provider.name)}</option>`).join("")}`;
  const credentialOptions = state.credentials.filter((credential) => credential.provider === "model_provider").map((credential) => `<option value="${credential.id}" ${row.credential_ref_id === credential.id ? "selected" : ""}>${escapeHtml(credential.name)}</option>`).join("");
  const gitlabCredentialOptions = `<option value="">创建时使用下方 Token 自动生成</option>${state.credentials.filter((credential) => credential.provider === "gitlab").map((credential) => `<option value="${credential.id}" ${row.credential_ref_id === credential.id ? "selected" : ""}>${escapeHtml(credential.name)}</option>`).join("")}`;
  const gitlabProfileOptions = state.gitlabProfiles.map((profile) => `<option value="${profile.id}" ${row.profile_id === profile.id ? "selected" : ""}>${escapeHtml(profile.name)}</option>`).join("");
  const projectCaseOptions = state.testCases.filter((testCase) => !row.project_id || testCase.project_id === row.project_id).map((testCase) => `<option value="${testCase.id}" ${row.case_ids?.includes(testCase.id) ? "selected" : ""}>${escapeHtml(testCase.name)}</option>`).join("");
  const suiteOptions = state.testSuites.map((suite) => `<option value="${suite.id}" ${row.suite_id === suite.id ? "selected" : ""}>${escapeHtml(suite.name)} · ${projectName(suite.project_id)}</option>`).join("");
  const environmentOptions = `<option value="">不绑定环境</option>${state.environments.map((env) => `<option value="${env.id}" ${row.environment_id === env.id ? "selected" : ""}>${escapeHtml(env.name)} · ${escapeHtml(env.type)}</option>`).join("")}`;
  const fileOptions = state.files.map((file) => `<option value="${file.id}" ${row.file_ids?.includes(file.id) ? "selected" : ""}>${escapeHtml(file.filename)}</option>`).join("");
  const runOptions = `<option value="">不绑定测试运行</option>${state.testRuns.map((run) => `<option value="${run.id}" ${row.test_run_id === run.id ? "selected" : ""}>${escapeHtml(run.id)} · ${translateStatus(run.status)}</option>`).join("")}`;
  const reportOptions = `<option value="">不绑定报告</option>${state.reports.map((report) => `<option value="${report.id}" ${row.last_report_id === report.id ? "selected" : ""}>${escapeHtml(report.title)}</option>`).join("")}`;
  const workflowVersions = row.id ? state.workflowVersions[row.id] || [] : [];
  const workflowVersionOptions = `<option value="">不激活版本</option>${workflowVersions.map((version) => `<option value="${version.id}" ${row.active_version_id === version.id ? "selected" : ""}>版本 ${escapeHtml(version.version)} · ${translateStatus(version.status)}</option>`).join("")}`;
  const submit = mode === "create" ? resourceConfig(type).action : "保存修改";
  if (type === "identity") return `<form class="form-grid"><label>姓名<input name="name" value="${escapeAttr(row.name)}" required /></label><label>邮箱<input name="email" type="email" value="${escapeAttr(row.email)}" required /></label><label>角色<select name="role">${selectedOptions(["Admin", "Operator", "Viewer"], row.roles?.[0]?.name || "Admin")}</select></label><label>范围<select name="scope">${selectedOptions(["platform", "project"], row.roles?.[0]?.scope || "platform")}</select></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "projects") return `<form class="form-grid"><label>项目编号<input name="key" value="${escapeAttr(row.key)}" required /></label><label>项目名称<input name="name" value="${escapeAttr(row.name)}" required /></label><label>负责人<select name="owner_id" required>${userOptions}</select></label><label>状态<select name="status">${selectedOptions(["active", "archived"], row.status || "active")}</select></label><label class="full">说明<textarea name="description">${escapeHtml(row.description || "")}</textarea></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "assets") return `<form class="form-grid"><label>资产名称<input name="name" value="${escapeAttr(row.name)}" required /></label><label>类别<select name="category">${selectedOptions(["server", "workstation", "vm", "gpu", "memory"], row.category || "server")}</select></label><label>状态<select name="status">${selectedOptions(["available", "in_use", "maintenance", "retired"], row.status || "available")}</select></label><label>负责人<select name="owner_id"><option value="">未分配</option>${userOptions}</select></label><label>父级资产<select name="parent_id">${assetOptions}</select></label><label>位置<input name="location" value="${escapeAttr(row.location)}" /></label><label class="full">能力标签<input name="capabilities" value="${escapeAttr((row.capabilities || []).join(", "))}" placeholder="cuda, linux, test-runner" /></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "gitlabProfiles") return `<form class="form-grid"><label>Profile 名称<input name="name" value="${escapeAttr(row.name)}" required /></label><label>Base URL<input name="base_url" value="${escapeAttr(row.base_url || "https://gitlab.example.com")}" required /></label><label>Credential Ref<select name="credential_ref_id">${gitlabCredentialOptions}</select></label><label>状态<select name="status">${selectedOptions(["active", "inactive"], row.status || "active")}</select></label><label class="full">GitLab Token ${mode === "create" ? "（未选择凭据时必填）" : "（编辑时不轮换）"}<input name="gitlab_secret" type="password" ${mode === "create" ? "" : "disabled"} placeholder="只提交到凭据 API，不在前端回显" /></label><label class="full">仓库选择<textarea name="repository_selection" placeholder="每行：id,path,name,web_url">${escapeHtml(repositoryLines(row.repository_selection || []))}</textarea></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "vcsOperations") return `<form class="form-grid"><label>Profile<select name="profile_id" required>${gitlabProfileOptions}</select></label><label>Repository ID<input name="repository_id" value="${escapeAttr(row.repository_id || firstRepositoryId())}" required /></label><label>操作<select name="operation_type">${selectedOptions(["create_branch", "open_merge_request", "merge_merge_request"], row.operation_type || "create_branch")}</select></label><label>分支<input name="branch" value="${escapeAttr(row.branch || "feature/operator-check")}" /></label><label>Source<input name="source_branch" value="${escapeAttr(row.source_branch || "feature/operator-check")}" /></label><label>Target<input name="target_branch" value="${escapeAttr(row.target_branch || "main")}" /></label><label class="full">MR 标题<input name="title" value="${escapeAttr(row.title || "前端控制台集成验证")}" /></label><label class="full">External ID<input name="external_id" value="${escapeAttr(row.external_id)}" placeholder="合并操作时填写 MR IID" /></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "vcsWebhooks") return `<form class="form-grid"><label>Profile<select name="profile_id" required>${gitlabProfileOptions}</select></label><label>Repository ID<input name="repository_id" value="${escapeAttr(row.repository_id || firstRepositoryId())}" /></label><label>事件类型<input name="event_type" value="${escapeAttr(row.event_type || "Pipeline Hook")}" required /></label><label>Authenticity Token<input name="authenticity_token" type="password" ${mode === "create" ? "required" : "disabled"} placeholder="只提交验证，不保存" /></label><label class="full">Payload JSON<textarea name="payload">${escapeHtml(JSON.stringify(row.payload || { status: "success", ref: "main" }))}</textarea></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "files") return `<form class="form-grid"><label>文件名<input name="filename" value="${escapeAttr(row.filename)}" required /></label><label>Content-Type<input name="content_type" value="${escapeAttr(row.content_type || "application/pdf")}" required /></label><label>大小 Bytes<input name="size_bytes" type="number" min="0" value="${escapeAttr(row.size_bytes || 0)}" required /></label><label>Owner<select name="owner_id"><option value="">系统</option>${userOptions}</select></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "testCases") return `<form class="form-grid"><label>项目<select name="project_id" required>${projectOptions}</select></label><label>用例名称<input name="name" value="${escapeAttr(row.name)}" required /></label><label>类型<select name="case_type">${selectedOptions(["manual", "automated"], row.case_type || "manual")}</select></label><label>优先级<select name="priority">${selectedOptions(["low", "medium", "high"], row.priority || "medium")}</select></label><label>状态<select name="status">${selectedOptions(["active", "inactive"], row.status || "active")}</select></label><label class="full">步骤<textarea name="steps" placeholder="每行：步骤 | 期望">${escapeHtml(stepLines(row.steps || []))}</textarea></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "testSuites") return `<form class="form-grid"><label>项目<select name="project_id" required>${projectOptions}</select></label><label>套件名称<input name="name" value="${escapeAttr(row.name)}" required /></label><label>状态<select name="status">${selectedOptions(["active", "inactive"], row.status || "active")}</select></label><label class="full">包含用例<select name="case_ids" multiple>${projectCaseOptions}</select></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "testRuns") return `<form class="form-grid"><label>项目<select name="project_id" required>${projectOptions}</select></label><label>套件<select name="suite_id" required>${suiteOptions}</select></label><label>环境<select name="environment_id">${environmentOptions}</select></label><label>状态<select name="status">${selectedOptions(["queued", "running", "passed", "failed", "cancelled"], row.status || "queued")}</select></label><label class="full">结果<textarea name="results" placeholder="每行：case_id,status">${escapeHtml(resultLines(row.results || []))}</textarea></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "reports") return `<form class="form-grid"><label>项目<select name="project_id" required>${projectOptions}</select></label><label>标题<input name="title" value="${escapeAttr(row.title)}" required /></label><label>类型<select name="report_type">${selectedOptions(["test", "qa", "qe", "operations"], row.report_type || "test")}</select></label><label>测试运行<select name="test_run_id">${runOptions}</select></label><label>状态<input name="status" value="${escapeAttr(row.status || "draft")}" /></label><label class="full">文件<select name="file_ids" multiple>${fileOptions}</select></label><label class="full">摘要 JSON<textarea name="summary">${escapeHtml(JSON.stringify(row.summary || {}))}</textarea></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "qualityGates") return `<form class="form-grid"><label>项目<select name="project_id" required>${projectOptions}</select></label><label>门禁名称<input name="name" value="${escapeAttr(row.name)}" required /></label><label>最近报告<select name="last_report_id">${reportOptions}</select></label><label>状态<select name="status">${selectedOptions(["pending", "passed", "failed", "waived"], row.status || "pending")}</select></label><label class="full">条件 JSON<textarea name="conditions">${escapeHtml(JSON.stringify(row.conditions || [{ metric: "failed", operator: "=", value: 0 }]))}</textarea></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "agents") return `<form class="form-grid"><label>智能体名称<input name="name" value="${escapeAttr(row.name)}" required /></label><label>类型<input name="kind" value="${escapeAttr(row.kind || "ops_controller")}" required /></label><label>状态<select name="status">${selectedOptions(["active", "inactive"], row.status || "active")}</select></label><label>模型供应商<select name="model_provider_id">${modelProviderOptions}</select></label><label class="full">关联 Skill<select name="skill_ids" multiple>${skillOptions}</select></label><label class="full">能力标签<input name="capabilities" value="${escapeAttr((row.capabilities || []).join(", "))}" placeholder="workflow, incident" /></label><label class="full">说明<textarea name="description">${escapeHtml(row.description || "")}</textarea></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "skills") return `<form class="form-grid"><label>Skill 名称<input name="name" value="${escapeAttr(row.name)}" required /></label><label>版本<input name="version" value="${escapeAttr(row.version || "1.0.0")}" required /></label><label>运行时<input name="runtime" value="${escapeAttr(row.runtime || "python")}" required /></label><label>状态<select name="status">${selectedOptions(["active", "deprecated"], row.status || "active")}</select></label><label class="full">能力标签<input name="capabilities" value="${escapeAttr((row.capabilities || []).join(", "))}" placeholder="readiness, deploy, audit" /></label><label class="full">包文件 ID<input name="package_file_id" value="${escapeAttr(row.package_file_id)}" placeholder="可选，来自文件中心" /></label><label class="full">说明<textarea name="description">${escapeHtml(row.description || "")}</textarea></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "credentials") return `<form class="form-grid"><label>Key 名称<input name="name" value="${escapeAttr(row.name)}" required /></label><label>状态<select name="status">${selectedOptions(["active", "inactive"], row.status || "active")}</select></label><label class="full">Secret ${mode === "create" ? "" : "（留空则不轮换）"}<input name="secret" type="password" ${mode === "create" ? "required" : ""} placeholder="只提交到后端，不在前端回显" /></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "modelProviders") return `<form class="form-grid"><label>供应商<input name="provider" value="${escapeAttr(row.provider || "deepseek")}" required /></label><label>名称<input name="name" value="${escapeAttr(row.name)}" required /></label><label>Credential Ref<select name="credential_ref_id" required>${credentialOptions}</select></label><label>状态<select name="status">${selectedOptions(["active", "inactive"], row.status || "active")}</select></label><label class="full">Base URL<input name="base_url" value="${escapeAttr(row.base_url)}" placeholder="https://api.deepseek.com" /></label><label class="full">模型列表<input name="models" value="${escapeAttr((row.models || []).join(", "))}" placeholder="deepseek-chat, deepseek-reasoner" /></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  if (type === "workflows") return `<form class="form-grid"><label>流程名称<input name="name" value="${escapeAttr(row.name)}" required /></label><label>项目<select name="project_id"><option value="">平台级流程</option>${projectOptions}</select></label><label>状态<select name="status">${selectedOptions(["draft", "active", "archived"], row.status || "draft")}</select></label><label>激活版本<select name="active_version_id">${workflowVersionOptions}</select></label><label class="full">说明<textarea name="description">${escapeHtml(row.description || "")}</textarea></label><button class="primary-button full" type="submit">${submit}</button></form>`;
  return `<form class="form-grid"><label>环境名称<input name="name" value="${escapeAttr(row.name)}" required /></label><label>类型<select name="type">${selectedOptions(["DEV", "QA", "QE"], row.type || "DEV")}</select></label><label>项目<select name="project_id" required>${projectOptions}</select></label><label>负责人<select name="owner_id" required>${userOptions}</select></label><label>状态<select name="status">${selectedOptions(["active", "inactive"], row.status || "active")}</select></label><label class="full">端点 URL<input name="endpoint" value="${escapeAttr(row.endpoints?.[0]?.url)}" placeholder="https://qa.example.local" /></label><button class="primary-button full" type="submit">${submit}</button></form>`;
}

async function submitForm(event, type, id) {
  event.preventDefault();
  try {
    const payload = payloadFromForm(new FormData(event.target), type);
    if (type === "gitlabProfiles" && !id) {
      await createGitLabProfile(payload);
      modal.close();
      await afterMutation(type);
      toast(`${resourceConfig(type).title}已保存。`);
      return;
    }
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
  if (type === "agents") {
    payload.skill_ids = form.getAll("skill_ids").filter(Boolean);
    payload.capabilities = csv(payload.capabilities);
    if (!payload.model_provider_id) payload.model_provider_id = "";
  }
  if (type === "skills") {
    payload.capabilities = csv(payload.capabilities);
    if (!payload.package_file_id) payload.package_file_id = "";
  }
  if (type === "credentials") {
    payload.provider = "model_provider";
    if (!payload.secret) delete payload.secret;
  }
  if (type === "modelProviders") {
    payload.models = csv(payload.models);
  }
  if (type === "workflows") {
    if (!payload.project_id) payload.project_id = "";
    if (!payload.active_version_id) payload.active_version_id = "";
  }
  if (type === "environments") {
    payload.member_ids = [];
    payload.asset_ids = [];
    payload.endpoints = payload.endpoint ? [{ name: "primary", url: payload.endpoint }] : [];
    delete payload.endpoint;
  }
  if (type === "gitlabProfiles") {
    payload.base_url = sanitizePublicUrl(payload.base_url, { allowPath: false });
    payload.repository_selection = repositorySelection(payload.repository_selection);
    if (!payload.credential_ref_id) delete payload.credential_ref_id;
    if (!payload.gitlab_secret) delete payload.gitlab_secret;
  }
  if (type === "vcsOperations") {
    payload.provider = "gitlab";
    for (const key of ["branch", "source_branch", "target_branch", "title", "external_id"]) {
      if (!payload[key]) delete payload[key];
    }
  }
  if (type === "vcsWebhooks") {
    payload.provider = "gitlab";
    payload.payload = redactClientPayload(jsonObject(payload.payload));
    if (!payload.repository_id) payload.repository_id = "";
    if (!payload.authenticity_token) delete payload.authenticity_token;
  }
  if (type === "files") {
    payload.size_bytes = Number(payload.size_bytes || 0);
    if (!payload.owner_id) payload.owner_id = "";
  }
  if (type === "testCases") {
    payload.steps = stepsFromText(payload.steps);
  }
  if (type === "testSuites") {
    payload.case_ids = form.getAll("case_ids").filter(Boolean);
  }
  if (type === "testRuns") {
    payload.results = resultsFromText(payload.results);
    if (!payload.environment_id) payload.environment_id = "";
  }
  if (type === "reports") {
    payload.file_ids = form.getAll("file_ids").filter(Boolean);
    payload.summary = jsonObject(payload.summary);
    if (!payload.test_run_id) payload.test_run_id = "";
  }
  if (type === "qualityGates") {
    payload.conditions = jsonArray(payload.conditions);
    if (!payload.last_report_id) payload.last_report_id = "";
  }
  return payload;
}

async function createGitLabProfile(payload) {
  const profilePayload = { ...payload };
  const secret = profilePayload.gitlab_secret;
  delete profilePayload.gitlab_secret;
  if (!profilePayload.credential_ref_id) {
    if (!secret) throw new Error("gitlab_profile_requires_credential_or_token");
    const credentialPayload = { provider: "gitlab", name: `${profilePayload.name} Token`, secret, status: "active" };
    if (state.apiOnline) {
      const credential = await apiRequest("POST", "/v1/credentials", credentialPayload);
      profilePayload.credential_ref_id = credential.id;
    } else {
      const credential = addLocal("credentials", credentialPayload);
      state.credentials.push(credential);
      addAudit("credentials.created", "credentials", credential.id);
      profilePayload.credential_ref_id = credential.id;
    }
  }
  if (state.apiOnline) await apiRequest("POST", endpoints.gitlabProfiles, profilePayload);
  else applyLocal("gitlabProfiles", null, () => addLocal("gitlabProfiles", profilePayload));
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
  if (actionName === "open-workflow-builder") return openWorkflowBuilder(id);
  if (actionName === "open-workflow-builder-preview") return openWorkflowBuilder(id, { preview: true });
  if (actionName === "create-workflow-version") return createWorkflowVersion(id, new FormData(form));
  if (actionName === "create-workflow-run" || actionName === "create-start-workflow-run") return createWorkflowRun(id, actionName === "create-start-workflow-run");
  if (actionName === "start-workflow-run") return startWorkflowRun(id);
  if (actionName === "update-workflow-step") return updateWorkflowStep(id, targetId);
  if (actionName?.startsWith("create-upload-") || actionName === "complete-upload-session" || actionName === "create-download-grant") return handleFileAction(actionName, id);
  const value = targetId || new FormData(form).get(actionValueKey(actionName));
  if (!value) return showError("请先选择需要绑定的记录。");
  if (actionName === "link-project-asset") await mutate("POST", `/v1/projects/${id}/assets/${value}`, undefined, "projects", id, (project) => ({ ...project, asset_ids: unique([...(project.asset_ids || []), value]) }));
  if (actionName === "unlink-project-asset") await mutate("DELETE", `/v1/projects/${id}/assets/${value}`, undefined, "projects", id, (project) => ({ ...project, asset_ids: (project.asset_ids || []).filter((assetId) => assetId !== value) }));
  if (actionName === "link-project-environment") await mutate("POST", `/v1/projects/${id}/environments/${value}`, undefined, "projects", id, (project) => ({ ...project, environment_ids: unique([...(project.environment_ids || []), value]) }));
  if (actionName === "unlink-project-environment") await mutate("DELETE", `/v1/projects/${id}/environments/${value}`, undefined, "projects", id, (project) => ({ ...project, environment_ids: (project.environment_ids || []).filter((envId) => envId !== value) }));
  if (actionName === "link-project-repository") {
    const [profileId, repositoryId] = value.split("|");
    await mutate("POST", `/v1/projects/${id}/repositories`, { provider: "gitlab", profile_id: profileId, repository_id: repositoryId }, "projects", id, (project) => ({ ...project, repository_bindings: uniqueRepositoryBindings([...(project.repository_bindings || []), repositoryBinding(profileId, repositoryId)]) }));
  }
  if (actionName === "unlink-project-repository") {
    const [profileId, repositoryId] = value.split("|");
    await mutate("DELETE", `/v1/projects/${id}/repositories/${profileId}/${repositoryId}`, undefined, "projects", id, (project) => ({ ...project, repository_bindings: (project.repository_bindings || []).filter((binding) => !(binding.profile_id === profileId && binding.repository_id === repositoryId)) }));
  }
  if (actionName === "bind-environment-asset") await patchEnvironment(id, (env) => ({ asset_ids: unique([...(env.asset_ids || []), value]) }));
  if (actionName === "unbind-environment-asset") await patchEnvironment(id, (env) => ({ asset_ids: (env.asset_ids || []).filter((assetId) => assetId !== value) }));
  if (actionName === "bind-environment-member") await patchEnvironment(id, (env) => ({ member_ids: unique([...(env.member_ids || []), value]) }));
  if (actionName === "unbind-environment-member") await patchEnvironment(id, (env) => ({ member_ids: (env.member_ids || []).filter((memberId) => memberId !== value) }));
  await afterMutation(state.route, id);
  toast("绑定关系已更新。");
}

async function handleFileAction(actionName, fileId) {
  if (!fileId) return showError("缺少文件 ID。");
  if (actionName === "create-upload-grant") {
    const grant = state.apiOnline ? await apiRequest("POST", `/v1/files/${fileId}/upload-grants`, {}) : localFileGrant(fileId, "PUT", "uploads");
    state.fileGrants[fileId] = { ...(state.fileGrants[fileId] || {}), upload: grant };
    state.detail = { type: "files", id: fileId };
    render();
    toast("上传授权已生成。");
    return;
  }
  if (actionName === "create-upload-session") {
    const session = state.apiOnline ? await apiRequest("POST", `/v1/files/${fileId}/upload-sessions`, {}) : localUploadSession(fileId);
    state.uploadSessions = [...state.uploadSessions.filter((item) => item.id !== session.id), session];
    state.detail = { type: "files", id: fileId };
    render();
    toast("上传会话已创建。");
    return;
  }
  if (actionName === "complete-upload-session") {
    const session = latestOpenUploadSession(fileId);
    if (!session) return showError("请先创建打开状态的上传会话。");
    const payload = { checksum: `sha256:${fileId.slice(-6)}`, size_bytes: state.files.find((file) => file.id === fileId)?.size_bytes || 0 };
    if (state.apiOnline) {
      const result = await apiRequest("POST", `/v1/files/upload-sessions/${session.id}/complete`, payload);
      state.uploadSessions = [...state.uploadSessions.filter((item) => item.id !== session.id), result.upload_session];
      const index = state.files.findIndex((item) => item.id === fileId);
      if (index >= 0) state.files[index] = result.file;
    } else {
      session.status = "completed";
      session.updated_at = new Date().toISOString();
      const file = state.files.find((item) => item.id === fileId);
      if (file) {
        file.status = "available";
        file.checksum = payload.checksum;
        file.updated_at = session.updated_at;
      }
    }
    state.detail = { type: "files", id: fileId };
    render();
    toast("上传会话已完成。");
    return;
  }
  const grant = state.apiOnline ? await apiRequest("POST", `/v1/files/${fileId}/download-grants`, {}) : localFileGrant(fileId, "GET", "downloads");
  state.fileGrants[fileId] = { ...(state.fileGrants[fileId] || {}), download: grant };
  state.detail = { type: "files", id: fileId };
  render();
  toast("下载授权已生成。");
}

async function createWorkflowVersion(workflowId, form) {
  const version = form.get("version");
  if (!version) return showError("请填写流程版本号。");
  const agentId = form.get("agent_id") || "";
  const skillId = form.get("skill_id") || "";
  const providerId = form.get("model_provider_id") || "";
  const nodes = [
    { id: "trigger", type: "trigger", name: "流程触发" },
    { id: "agent-task", type: "agent_task", name: "智能体执行", agent_id: agentId, skill_id: skillId, model_provider_id: providerId },
    { id: "approval", type: "approval", name: "人工确认" },
  ].map((node) => Object.fromEntries(Object.entries(node).filter(([, value]) => value !== "")));
  const payload = {
    version,
    status: form.get("status") || "draft",
    nodes,
    edges: [
      { from_node_id: "trigger", to_node_id: "agent-task" },
      { from_node_id: "agent-task", to_node_id: "approval" },
    ],
  };
  if (state.apiOnline) await apiRequest("POST", `/v1/workflows/${workflowId}/versions`, payload);
  else {
    const item = { ...payload, id: `wfv_local_${Date.now()}`, workflow_id: workflowId, created_at: new Date().toISOString(), updated_at: new Date().toISOString() };
    state.workflowVersions[workflowId] = [...(state.workflowVersions[workflowId] || []), item];
    const workflow = state.workflows.find((row) => row.id === workflowId);
    if (workflow && !workflow.active_version_id) workflow.active_version_id = item.id;
  }
  await afterMutation("workflows", workflowId);
  toast("流程版本已创建。");
}

async function createWorkflowRun(workflowId, start = false) {
  const workflow = state.workflows.find((row) => row.id === workflowId);
  if (!workflow) return showError("未找到流程定义。");
  const activeVersion = activeWorkflowVersion(workflow);
  if (!activeVersion) return showError("当前流程没有激活版本，无法创建运行。");
  if (state.apiOnline) {
    await apiRequest("POST", `/v1/workflows/${workflowId}/runs`, { workflow_version_id: activeVersion.id, trigger_type: "manual", start });
    state.detail = { type: "workflows", id: workflowId };
    await loadData();
  } else {
    const run = localWorkflowRun(workflow, activeVersion);
    state.workflowRuns = [run, ...state.workflowRuns];
    if (start) localStartWorkflowRun(run.id);
    state.detail = { type: "workflows", id: workflowId };
    render();
  }
  toast(start ? "运行已创建并启动。" : "运行已创建，等待手动启动。");
}

async function startWorkflowRun(runId) {
  const run = state.workflowRuns.find((item) => item.id === runId);
  if (!run) return showError("未找到运行实例。");
  if (state.apiOnline) {
    await apiRequest("POST", `/v1/workflow-runs/${runId}/start`);
    state.detail = { type: "workflows", id: run.workflow_id };
    await loadData();
  } else {
    localStartWorkflowRun(runId);
    state.detail = { type: "workflows", id: run.workflow_id };
    render();
  }
  toast("运行已启动。");
}

async function updateWorkflowStep(runId, target) {
  const [stepRunId, status] = String(target || "").split("|");
  if (!stepRunId || !status) return showError("缺少步骤流转参数。");
  const run = state.workflowRuns.find((item) => item.id === runId);
  if (!run) return showError("未找到运行实例。");
  const step = (run.steps || []).find((item) => item.id === stepRunId);
  if (!step) return showError("未找到步骤实例。");
  const payload = workflowStepUpdatePayload(step, status);
  if (state.apiOnline) {
    await apiRequest("PATCH", `/v1/workflow-runs/${runId}/steps/${stepRunId}`, payload);
    state.detail = { type: "workflows", id: run.workflow_id };
    await loadData();
  } else {
    localUpdateWorkflowStep(runId, stepRunId, payload);
    state.detail = { type: "workflows", id: run.workflow_id };
    render();
  }
  toast(`步骤已${translateStatus(status)}。`);
}

function workflowStepUpdatePayload(step, status) {
  const payload = { status };
  if (status === "completed") payload.output = { message: "前端控制台确认完成", step_type: step.step_type, node_id: step.node_id };
  if (status === "failed") payload.error = step.step_type === "manual" ? "人工拒绝，流程停止。" : "前端控制台标记失败。";
  if (status === "skipped") payload.output = { reason: "前端控制台跳过该步骤", step_type: step.step_type };
  return payload;
}

function localWorkflowRun(workflow, version) {
  const now = new Date().toISOString();
  const runId = `wfr_local_${Date.now()}`;
  const predecessors = workflowPredecessorSnapshot(version);
  const steps = workflowOrderedNodes(version).map((node, index) => ({
    id: `wfs_local_${Date.now()}_${index + 1}`,
    workflow_run_id: runId,
    workflow_id: workflow.id,
    workflow_version_id: version.id,
    node_id: String(node.id),
    node_type: String(node.type),
    step_type: workflowNodeStepType(node.type),
    sequence: index + 1,
    name: String(node.name || workflowNodeTypeLabel(node.type)),
    agent_id: node.agent_id || "",
    skill_id: node.skill_id || "",
    model_provider_id: node.model_provider_id || "",
    predecessor_node_ids: predecessors[String(node.id)] || [],
    input: Object.fromEntries(Object.entries(node).filter(([key]) => !["id", "type", "name"].includes(key))),
    status: "pending",
    created_at: now,
    updated_at: now,
  }));
  return { id: runId, workflow_id: workflow.id, workflow_version_id: version.id, trigger_type: "manual", status: "created", steps, created_at: now, updated_at: now };
}

function localStartWorkflowRun(runId) {
  const run = state.workflowRuns.find((item) => item.id === runId);
  if (!run) throw new Error("workflow run not found");
  if (run.status !== "created") throw new Error("workflow run cannot be started from current status");
  const now = new Date().toISOString();
  run.status = "running";
  run.started_at = now;
  run.updated_at = now;
  (run.steps || []).forEach((step) => {
    if (step.step_type === "trigger") {
      step.status = "completed";
      step.started_at = now;
      step.completed_at = now;
      step.updated_at = now;
      step.output = step.output || { trigger: "manual" };
    }
  });
  localRefreshWorkflowRunStatus(run);
}

function localUpdateWorkflowStep(runId, stepRunId, payload) {
  const run = state.workflowRuns.find((item) => item.id === runId);
  if (!run) throw new Error("workflow run not found");
  if (run.status !== "running") throw new Error("workflow run is not active");
  const step = (run.steps || []).find((item) => item.id === stepRunId);
  if (!step) throw new Error("workflow step run not found");
  if (step.step_type === "trigger") throw new Error("trigger step runs are managed by workflow start");
  const gate = workflowStepGateState(run, step);
  const allowed = workflowAllowedStepStatuses(run, step, gate);
  if (!allowed.includes(payload.status)) {
    if (!gate.ready) throw new Error("前置节点尚未满足，不能流转该步骤。");
    throw new Error("workflow step cannot transition from current status");
  }
  const now = new Date().toISOString();
  if (payload.status === "running" && !step.started_at) step.started_at = now;
  if (["completed", "failed", "skipped"].includes(payload.status)) {
    step.completed_at = now;
    step.started_at = step.started_at || now;
  }
  step.status = payload.status;
  if ("output" in payload) step.output = payload.output;
  if ("error" in payload) step.error = payload.error;
  step.updated_at = now;
  localRefreshWorkflowRunStatus(run);
}

function localRefreshWorkflowRunStatus(run) {
  const now = new Date().toISOString();
  const executableSteps = (run.steps || []).filter((step) => step.step_type !== "trigger");
  if (executableSteps.some((step) => step.status === "failed")) {
    run.status = "failed";
    run.completed_at = run.completed_at || now;
    run.updated_at = run.completed_at;
    return;
  }
  if (executableSteps.length && executableSteps.every((step) => ["completed", "skipped"].includes(step.status))) {
    run.status = "completed";
    run.completed_at = run.completed_at || now;
    run.updated_at = run.completed_at;
    return;
  }
  if (run.status !== "created") {
    run.status = "running";
    run.updated_at = now;
  }
}

function workflowOrderedNodes(version) {
  const nodes = (version.nodes || []).map((node) => ({ ...node }));
  const byId = Object.fromEntries(nodes.map((node) => [String(node.id), node]));
  const incoming = Object.fromEntries(nodes.map((node) => [String(node.id), 0]));
  const outgoing = Object.fromEntries(nodes.map((node) => [String(node.id), []]));
  for (const edge of version.edges || []) {
    const from = String(edge.from_node_id);
    const to = String(edge.to_node_id);
    if (!byId[from] || !byId[to]) continue;
    outgoing[from].push(to);
    incoming[to] += 1;
  }
  const queue = nodes.filter((node) => incoming[String(node.id)] === 0).map((node) => String(node.id));
  const ordered = [];
  while (queue.length) {
    const id = queue.shift();
    ordered.push(byId[id]);
    for (const target of outgoing[id] || []) {
      incoming[target] -= 1;
      if (incoming[target] === 0) queue.push(target);
    }
  }
  return ordered.length === nodes.length ? ordered : workflowExecutionOrder(version);
}

function workflowPredecessorSnapshot(version) {
  const predecessors = Object.fromEntries((version.nodes || []).map((node) => [String(node.id), []]));
  for (const edge of version.edges || []) {
    const from = String(edge.from_node_id);
    const to = String(edge.to_node_id);
    if (predecessors[to] && Object.prototype.hasOwnProperty.call(predecessors, from)) predecessors[to].push(from);
  }
  return predecessors;
}

function workflowNodeStepType(type) {
  if (type === "trigger") return "trigger";
  if (type === "agent_task") return "agent";
  if (["approval", "manual", "manual_task"].includes(type)) return "manual";
  return "result";
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
    state[collection].push(sanitizeLocalItem(type, localChange()));
    addAudit(`${collection}.created`, collection, state[collection].at(-1).id);
    return;
  }
  const index = state[collection].findIndex((item) => item.id === id);
  if (index < 0) return;
  const updated = localChange(state[collection][index]);
  if (updated === null) state[collection].splice(index, 1);
  else state[collection][index] = sanitizeLocalItem(type, updated, state[collection][index]);
  addAudit(`${collection}.updated`, collection, id);
}

function addLocal(type, payload) {
  const idPrefix = { identity: "usr", projects: "prj", assets: "ast", environments: "env", gitlabProfiles: "glp", vcsOperations: "vcs", vcsWebhooks: "whk", files: "fil", testCases: "tca", testSuites: "tsu", testRuns: "trn", reports: "rpt", qualityGates: "qgt", agents: "agt", skills: "skl", credentials: "crd", modelProviders: "mdl", workflows: "wfl" }[type];
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
  if (type === "credentials") {
    return sanitizeCredential(item, {}, { local: true });
  }
  if (type === "gitlabProfiles") {
    Object.assign(item, sanitizeGitLabProfile(item, { strict: true }));
    state.gitlabRepositories[item.id] = item.repository_selection.length ? item.repository_selection : [
      { id: "stub-ops-platform", path: "platform/opspilot", name: "OpsPilot", web_url: `${item.base_url.replace(/\/$/, "")}/platform/opspilot` },
      { id: "stub-infra", path: "platform/infra", name: "Infra", web_url: `${item.base_url.replace(/\/$/, "")}/platform/infra` },
    ];
  }
  if (type === "vcsOperations") {
    item.provider = "gitlab";
    item.status = "completed";
    item.external_id = item.external_id || `local-${item.operation_type}-${item.repository_id}`;
    item.result = { adapter: "local_stub", repository_id: item.repository_id, repository_path: repositoryName(item.profile_id, item.repository_id, false) };
  }
  if (type === "vcsWebhooks") {
    item.provider = "gitlab";
    item.status = item.status || "received";
    item.payload = redactClientPayload(item.payload || {});
    delete item.authenticity_token;
  }
  if (type === "files") {
    item.status = "pending_upload";
    item.checksum = "";
  }
  if (type === "testCases") item.steps = item.steps || [];
  if (type === "testSuites") item.case_ids = unique(item.case_ids || []);
  if (type === "testRuns") item.results = item.results || [];
  if (type === "reports") {
    item.file_ids = unique(item.file_ids || []);
    item.summary = item.summary || {};
  }
  if (type === "qualityGates") item.conditions = item.conditions || [];
  if (type === "workflows") {
    item.active_version_id = item.active_version_id || "";
    state.workflowVersions[item.id] = [];
  }
  return item;
}

function sanitizeLocalItem(type, item, previous = {}) {
  return type === "credentials" ? sanitizeCredential(item, previous, { local: true }) : item;
}

function sanitizeCredential(item = {}, previous = {}, options = {}) {
  const safe = { ...item };
  const hadSecret = Object.prototype.hasOwnProperty.call(safe, "secret") && Boolean(safe.secret);
  delete safe.secret;
  safe.provider = safe.provider || previous.provider || "model_provider";
  if (options.local) {
    safe.secret_ref = safe.secret_ref || previous.secret_ref || `vault://local/${safe.id || "pending"}`;
    safe.secret_fingerprint = hadSecret || !safe.secret_fingerprint ? `fp_${String(Date.now()).slice(-6)}` : safe.secret_fingerprint;
  }
  return safe;
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
  const tone = ["active", "available", "in_use", "done", "completed", "passed", "skipped", "available"].includes(status) ? "ok" : ["inactive", "maintenance", "archived", "warning", "pending", "created", "queued", "low", "medium", "draft", "deprecated", "pending_upload", "open", "received"].includes(status) ? "warn" : ["high", "retired", "failed", "cancelled", "rejected"].includes(status) ? "bad" : status === "running" ? "" : "";
  return `<span class="pill ${tone}">${escapeHtml(translateStatus(status))}</span>`;
}

function roles(value = []) {
  return value.length ? value.map((role) => `<span class="role-pill">${escapeHtml(role.scope)}:${displayRole(role.name)}</span>`).join(" ") : `<span class="muted">暂无角色</span>`;
}

function tags(value = []) {
  return value.length ? value.map((tag) => `<span class="pill">${escapeHtml(tag)}</span>`).join(" ") : `<span class="muted">暂无</span>`;
}

function options(items, emptyLabel) {
  return items.length ? items.map((item) => `<option value="${item.id}">${labelFor(collectionNameForItem(item), item.id, false)}</option>`).join("") : `<option value="">${emptyLabel}</option>`;
}

function selectedOptions(values, selected) {
  return values.map((value) => `<option ${value === selected ? "selected" : ""}>${value}</option>`).join("");
}

function nameFor(collection, id) {
  return escapeHtml((state[collection] || []).find((item) => item.id === id)?.name || id || "未分配");
}

function projectName(id) {
  const project = state.projects.find((item) => item.id === id);
  return escapeHtml(project ? `${project.key} · ${project.name}` : id || "平台级流程");
}

function assetLabel(id) {
  return escapeHtml(state.assets.find((item) => item.id === id)?.name || id);
}

function projectEnvLabel(id) {
  return `环境 ${escapeHtml(state.environments.find((item) => item.id === id)?.name || id)}`;
}

function displayTitle(type, row) {
  if (type === "vcsOperations") return translateOperation(row.operation_type);
  if (type === "files") return row.filename;
  if (type === "testRuns") return `测试运行 ${row.id}`;
  return row.name || row.title || row.key || row.email || row.id;
}

function labelFor(source, id, safe = true) {
  const maps = {
    users: state.users,
    assets: state.assets,
    environments: state.environments,
    projects: state.projects,
    gitlabProfiles: state.gitlabProfiles,
    files: state.files,
    testCases: state.testCases,
    testSuites: state.testSuites,
    testRuns: state.testRuns,
    reports: state.reports,
    qualityGates: state.qualityGates,
    skills: state.skills,
    credentials: state.credentials,
    modelProviders: state.modelProviders,
    workflows: state.workflows,
    agents: state.agents,
  };
  const item = maps[source]?.find((row) => row.id === id);
  const label = item?.key ? `${item.key} · ${item.name}` : item?.name || item?.email || id;
  return safe ? escapeHtml(label) : label;
}

function collectionNameForItem(item) {
  if ("email" in item) return "users";
  if ("category" in item) return "assets";
  if ("type" in item && "project_id" in item) return "environments";
  if ("base_url" in item && "credential_ref_id" in item) return "gitlabProfiles";
  if ("filename" in item && "content_type" in item) return "files";
  if ("case_type" in item && "steps" in item) return "testCases";
  if ("case_ids" in item) return "testSuites";
  if ("suite_id" in item && "results" in item) return "testRuns";
  if ("report_type" in item) return "reports";
  if ("conditions" in item) return "qualityGates";
  if ("runtime" in item && "version" in item) return "skills";
  if ("secret_ref" in item) return "credentials";
  if ("credential_ref_id" in item && "models" in item) return "modelProviders";
  if ("kind" in item && "skill_ids" in item) return "agents";
  if ("active_version_id" in item) return "workflows";
  return "projects";
}

function skillName(id) {
  const skill = state.skills.find((item) => item.id === id);
  return escapeHtml(skill ? `${skill.name} · ${skill.version}` : id || "未绑定");
}

function modelProviderName(id) {
  const provider = state.modelProviders.find((item) => item.id === id);
  return escapeHtml(provider ? `${provider.provider} · ${provider.name}` : id || "未绑定");
}

function credentialName(id) {
  const credential = state.credentials.find((item) => item.id === id);
  return escapeHtml(credential ? credential.name : id || "未绑定");
}

function gitlabProfileName(id) {
  const profile = state.gitlabProfiles.find((item) => item.id === id);
  return escapeHtml(profile ? profile.name : id || "未绑定");
}

function repositoryName(profileId, repositoryId, safe = true) {
  const repository = (state.gitlabRepositories[profileId] || []).find((item) => item.id === repositoryId);
  const label = repository ? `${repository.path} (${repository.id})` : repositoryId || "未选择";
  return safe ? escapeHtml(label) : label;
}

function testCaseName(id) {
  const testCase = state.testCases.find((item) => item.id === id);
  return escapeHtml(testCase ? testCase.name : id || "未绑定");
}

function testSuiteName(id) {
  const suite = state.testSuites.find((item) => item.id === id);
  return escapeHtml(suite ? suite.name : id || "未绑定");
}

function testRunName(id) {
  const run = state.testRuns.find((item) => item.id === id);
  return escapeHtml(run ? `运行 ${run.id}` : id || "未绑定");
}

function reportName(id) {
  const report = state.reports.find((item) => item.id === id);
  return escapeHtml(report ? report.title : id || "未绑定");
}

function environmentName(id) {
  const env = state.environments.find((item) => item.id === id);
  return escapeHtml(env ? `${env.name} · ${env.type}` : id || "未绑定");
}

function linkedNameList(ids, source) {
  return ids.length ? ids.map((id) => `<span class="pill">${labelFor(source, id)}</span>`).join(" ") : `<span class="muted">暂无绑定</span>`;
}

function workflowNodeCount(workflowId) {
  return (state.workflowVersions[workflowId] || []).reduce((total, version) => total + (version.nodes?.length || 0), 0);
}

function repositoryList(profileId) {
  const repositories = state.gitlabRepositories[profileId] || [];
  return repositories.length ? `<ul class="link-list">${repositories.map((repo) => `<li><span>${escapeHtml(repo.path)} · ${escapeHtml(repo.web_url)}</span></li>`).join("")}</ul>` : `<div class="empty-state compact">暂无仓库选择。</div>`;
}

function repositoryBindingOptions(project) {
  const existing = new Set((project.repository_bindings || []).map((binding) => `${binding.profile_id}|${binding.repository_id}`));
  const options = state.gitlabProfiles.flatMap((profile) => (state.gitlabRepositories[profile.id] || []).map((repo) => ({ profile, repo }))).filter(({ profile, repo }) => !existing.has(`${profile.id}|${repo.id}`));
  return options.length ? options.map(({ profile, repo }) => `<option value="${profile.id}|${repo.id}">${escapeHtml(profile.name)} · ${escapeHtml(repo.path)}</option>`).join("") : `<option value="">没有可绑定仓库</option>`;
}

function repositoryBindingList(project) {
  const bindings = project.repository_bindings || [];
  return bindings.length ? `<ul class="link-list">${bindings.map((binding) => `<li><span>${repositoryName(binding.profile_id, binding.repository_id)}</span>${actionButton("link", "解绑", "ghost-button small", `unlink-repository-${binding.profile_id}-${binding.repository_id}`, { actionName: "unlink-project-repository", id: project.id, targetId: `${binding.profile_id}|${binding.repository_id}` })}</li>`).join("")}</ul>` : `<div class="empty-state compact">暂无仓库绑定。</div>`;
}

function repositoryBinding(profileId, repositoryId) {
  const repo = (state.gitlabRepositories[profileId] || []).find((item) => item.id === repositoryId) || {};
  return { provider: "gitlab", profile_id: profileId, repository_id: repositoryId, path: repo.path || "", web_url: repo.web_url || "" };
}

function uniqueRepositoryBindings(bindings) {
  const seen = new Set();
  return bindings.filter((binding) => {
    const key = `${binding.profile_id}|${binding.repository_id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function fileActionPanel(file) {
  return `
    <h4>上传/下载控制</h4>
    <div class="action-row">
      ${actionButton("link", "上传授权", "ghost-button small", `detail-upload-grant-${file.id}`, { actionName: "create-upload-grant", id: file.id })}
      ${actionButton("link", "上传会话", "ghost-button small", `detail-upload-session-${file.id}`, { actionName: "create-upload-session", id: file.id })}
      ${actionButton("link", "完成上传", "ghost-button small", `detail-complete-upload-${file.id}`, { actionName: "complete-upload-session", id: file.id })}
      ${actionButton("link", "下载授权", "ghost-button small", `detail-download-grant-${file.id}`, { actionName: "create-download-grant", id: file.id })}
    </div>
    ${fileGrantSummary(file.id)}
  `;
}

function fileGrantSummary(fileId) {
  const grant = state.fileGrants[fileId] || {};
  const sessions = state.uploadSessions.filter((session) => session.file_id === fileId);
  return listItems([
    grant.upload ? `上传授权 ${escapeHtml(grant.upload.method)} · ${grant.upload.expires_in_seconds || 0} 秒有效` : "暂无上传授权",
    grant.download ? `下载授权 ${escapeHtml(grant.download.method)} · ${grant.download.expires_in_seconds || 0} 秒有效` : "暂无下载授权",
    sessions.length ? `上传会话 ${escapeHtml(sessions.at(-1).id)} · ${statusPill(sessions.at(-1).status)} · ${sessions.at(-1).expires_in_seconds || 0} 秒有效` : "暂无上传会话",
  ]);
}

function fileUploadState(file) {
  const session = latestUploadSession(file.id);
  return session ? statusPill(session.status) : `<span class="muted">未创建会话</span>`;
}

function latestUploadSession(fileId) {
  return state.uploadSessions.filter((session) => session.file_id === fileId).at(-1);
}

function latestOpenUploadSession(fileId) {
  return state.uploadSessions.filter((session) => session.file_id === fileId && session.status === "open").at(-1);
}

function localFileGrant(fileId, method, scope) {
  return { file_id: fileId, method, url: `local://${scope}/objects/${fileId}`, expires_in_seconds: 900 };
}

function localUploadSession(fileId) {
  const now = new Date().toISOString();
  return { id: `upl_local_${Date.now()}`, file_id: fileId, method: "PUT", status: "open", url: `local://uploads/objects/${fileId}`, expires_in_seconds: 900, created_at: now, updated_at: now };
}

function firstRepositoryId() {
  const profile = state.gitlabProfiles[0];
  return profile ? (state.gitlabRepositories[profile.id] || [])[0]?.id || "" : "";
}

function repositoryLines(repositories) {
  return repositories.map((repo) => [repo.id, repo.path, repo.name, repo.web_url].filter(Boolean).join(",")).join("\n");
}

function repositorySelection(value) {
  return String(value || "").split(/\n+/).map((line) => line.trim()).filter(Boolean).map((line) => {
    const [id, path, name, webUrl] = line.split(",").map((part) => part.trim());
    return { id, path, name: name || path, web_url: webUrl ? sanitizePublicUrl(webUrl, { allowPath: true }) : "" };
  }).filter((repo) => repo.id && repo.path);
}

function stepLines(steps) {
  return steps.map((step) => [step.name, step.expected].filter(Boolean).join(" | ")).join("\n");
}

function stepsFromText(value) {
  return String(value || "").split(/\n+/).map((line) => line.trim()).filter(Boolean).map((line) => {
    const [name, expected] = line.split("|").map((part) => part.trim());
    return { name, expected: expected || "" };
  });
}

function resultLines(results) {
  return results.map((result) => [result.case_id, result.status].filter(Boolean).join(",")).join("\n");
}

function resultsFromText(value) {
  return String(value || "").split(/\n+/).map((line) => line.trim()).filter(Boolean).map((line) => {
    const [caseId, status] = line.split(",").map((part) => part.trim());
    return { case_id: caseId, status: status || "passed" };
  }).filter((result) => result.case_id);
}

function jsonObject(value) {
  try {
    const parsed = JSON.parse(value || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function jsonArray(value) {
  try {
    const parsed = JSON.parse(value || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function sanitizeGitLabProfile(profile = {}, options = {}) {
  const safe = { ...profile };
  try {
    safe.base_url = sanitizePublicUrl(safe.base_url || "", { allowPath: false });
  } catch (error) {
    if (options.strict) throw error;
    safe.base_url = "已拒绝的 URL";
  }
  safe.repository_selection = (safe.repository_selection || []).map((repository) => sanitizeGitLabRepository(repository, safe.base_url, options)).filter(Boolean);
  return safe;
}

function sanitizeGitLabRepositoryMap(repositoryMap = {}) {
  return Object.fromEntries(Object.entries(repositoryMap).map(([profileId, repositories]) => {
    const profile = state.gitlabProfiles.find((item) => item.id === profileId);
    return [profileId, (repositories || []).map((repository) => sanitizeGitLabRepository(repository, profile?.base_url || "")).filter(Boolean)];
  }));
}

function sanitizeGitLabRepository(repository = {}, baseUrl = "", options = {}) {
  const safe = { ...repository };
  try {
    if (safe.web_url) safe.web_url = sanitizePublicUrl(safe.web_url, { allowPath: true });
    else if (baseUrl && safe.path && baseUrl !== "已拒绝的 URL") safe.web_url = `${baseUrl.replace(/\/$/, "")}/${String(safe.path).replace(/^\//, "")}`;
  } catch (error) {
    if (options.strict) throw error;
    safe.web_url = "已拒绝的 URL";
  }
  return safe;
}

function sanitizeWebhookEvent(event = {}) {
  const safe = { ...event };
  safe.payload = redactClientPayload(safe.payload || {});
  delete safe.authenticity_token;
  return safe;
}

function sanitizePublicUrl(value, options = {}) {
  let parsed;
  try {
    parsed = new URL(String(value || "").trim());
  } catch {
    throw new Error("invalid_url");
  }
  if (!["http:", "https:"].includes(parsed.protocol) || !parsed.host) throw new Error("invalid_url");
  if (parsed.username || parsed.password || parsed.hash) throw new Error("sensitive_url_rejected");
  for (const key of parsed.searchParams.keys()) {
    const lowered = key.toLowerCase();
    if (["access_token", "auth_token", "api_token", "private_token", "token", "key", "secret", "password"].includes(lowered) || ["token", "secret", "password", "key"].some((part) => lowered.includes(part))) throw new Error("sensitive_url_rejected");
  }
  const path = options.allowPath ? parsed.pathname.replace(/\/$/, "") : "";
  return `${parsed.protocol}//${parsed.host}${path}`;
}

function redactClientPayload(value) {
  if (Array.isArray(value)) return value.map(redactClientPayload);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => {
      const lowered = key.toLowerCase();
      const sensitive = ["token", "secret", "password", "key", "authorization", "cookie"].some((part) => lowered.includes(part));
      return [key, sensitive ? "[REDACTED]" : redactClientPayload(item)];
    }));
  }
  return typeof value === "string" ? redactSensitiveString(value) : value;
}

function redactSensitiveString(value) {
  return String(value || "")
    .replace(/\b(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;]+/gi, "$1[REDACTED]")
    .replace(/\b((?:api[_-]?key|access[_-]?token|auth[_-]?token|private[_-]?token|token|secret|password)\s*[:=]\s*)[^\s,;&]+/gi, "$1[REDACTED]")
    .replace(/\b(cookie\s*[:=]\s*)[^\n]+/gi, "$1[REDACTED]")
    .replace(/(\b(?:session|sid|csrf|xsrf|jwt|auth|token)[A-Za-z0-9_.-]*=)[^;\s]+/gi, "$1[REDACTED]");
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function translateOperation(value) {
  return { create_branch: "创建分支", open_merge_request: "创建 MR", merge_merge_request: "合并 MR" }[value] || value || "VCS 操作";
}

function csv(value) {
  return String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
}

function listItems(items) {
  return items.length ? `<ul class="link-list">${items.map((item) => `<li>${item}</li>`).join("")}</ul>` : `<div class="empty-state compact">暂无相关记录。</div>`;
}

function jsonBlock(value) {
  return `<pre class="json-block">${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
}

function activeCount(items) {
  return items.filter((item) => item.status === "active").length;
}

function linkedProjects() {
  return state.projects.filter((project) => project.asset_ids?.length || project.environment_ids?.length).length;
}

function countFor(key) {
  return { dashboard: "", bigscreen: "", tasks: "", identity: state.users.length, projects: state.projects.length, assets: state.assets.length, environments: state.environments.length, gitlabProfiles: state.gitlabProfiles.length, vcsOperations: state.vcsOperations.length, vcsWebhooks: state.vcsWebhooks.length, files: state.files.length, testCases: state.testCases.length, testSuites: state.testSuites.length, testRuns: state.testRuns.length, reports: state.reports.length, qualityGates: state.qualityGates.length, agents: state.agents.length, skills: state.skills.length, credentials: state.credentials.filter((row) => row.provider === "model_provider").length, modelProviders: state.modelProviders.length, workflows: state.workflows.length }[key] || "";
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
  if (type === "gitlabProfiles") return row.status === "inactive" ? "启用" : "停用";
  if (type === "testRuns") return row.status === "passed" ? "重跑" : "推进";
  if (type === "agents") return row.status === "inactive" ? "启用" : "停用";
  if (type === "skills") return row.status === "deprecated" ? "恢复" : "废弃";
  if (type === "credentials") return row.status === "inactive" ? "启用" : "停用";
  if (type === "modelProviders") return row.status === "inactive" ? "启用" : "停用";
  if (type === "workflows") return row.status === "archived" ? "恢复" : "归档";
  return "";
}

function nextStatusFor(type, row) {
  if (type === "identity") return row.status === "inactive" ? "active" : "inactive";
  if (type === "projects") return row.status === "archived" ? "active" : "archived";
  if (type === "assets") return row.status === "retired" ? "available" : "retired";
  if (type === "environments") return row.status === "inactive" ? "active" : "inactive";
  if (type === "gitlabProfiles") return row.status === "inactive" ? "active" : "inactive";
  if (type === "testRuns") return { queued: "running", running: "passed", passed: "queued", failed: "queued", cancelled: "queued" }[row.status] || "running";
  if (type === "agents") return row.status === "inactive" ? "active" : "inactive";
  if (type === "skills") return row.status === "deprecated" ? "active" : "deprecated";
  if (type === "credentials") return row.status === "inactive" ? "active" : "inactive";
  if (type === "modelProviders") return row.status === "inactive" ? "active" : "inactive";
  if (type === "workflows") return row.status === "archived" ? "active" : "archived";
  return row.status || "active";
}

function supportsEdit(type) {
  return !["vcsOperations", "files", "testCases", "testSuites", "reports", "qualityGates"].includes(type);
}

function supportsDelete(type) {
  return ["identity", "projects", "assets", "environments", "gitlabProfiles", "agents", "skills", "credentials", "modelProviders", "workflows"].includes(type);
}

function actionValueKey(actionName) {
  if (actionName.includes("asset")) return "asset_id";
  if (actionName.includes("environment")) return "environment_id";
  if (actionName.includes("repository")) return "repository_binding";
  return "member_id";
}

function addAudit(action, resourceType, resourceId) {
  state.auditEvents.unshift({ id: `aud_local_${Date.now()}`, actor_id: ACTOR_ID, action, resource_type: resourceType, resource_id: resourceId, occurred_at: new Date().toISOString(), metadata: {} });
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function date(value) {
  if (!value) return "未记录";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(value));
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
    draft: "草稿",
    deprecated: "已废弃",
    high: "高",
    medium: "中",
    warning: "中",
    low: "低",
    manual: "手工",
    automated: "自动化",
    pending_upload: "待上传",
    completed: "已完成",
    passed: "通过",
    failed: "失败",
    cancelled: "已取消",
    received: "已接收",
    processed: "已处理",
    rejected: "已拒绝",
    open: "打开",
    published: "已发布",
    running: "运行中",
    created: "已创建",
    skipped: "已跳过",
    pending: "等待人工处理",
    done: "已完成",
    queued: "待分配",
  }[status] || status;
}

function overviewTable() {
  const rows = state.apiOnline ? state.projects.map(projectOverviewRow) : [
    ["智能运营中台", "王少琪", "2 个警告", "98% 在线", "10 分钟前"],
    ["自动化测试平台", "李伟", "正常", "96% 在线", "32 分钟前"],
    ["模型服务网关", "陈敏", "1 个阻塞", "99% 在线", "1 小时前"],
  ];
  if (!rows.length) return "";
  return `<table><thead><tr>${["项目", "负责人", "环境健康", "资产状态", "最近变更"].map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

function projectOverviewRow(project) {
  const owner = state.users.find((user) => user.id === project.owner_id);
  const environments = state.environments.filter((env) => (project.environment_ids || []).includes(env.id));
  const issues = environments.filter((env) => readiness(env).level !== "ok");
  const assetCount = (project.asset_ids || []).length;
  return [
    escapeHtml(project.name),
    escapeHtml(owner?.name || "未分配"),
    environments.length ? issues.length ? `${issues.length} 个警告` : "正常" : "未配置环境",
    assetCount ? `${assetCount} 个资产` : "未绑定资产",
    date(project.updated_at),
  ];
}

function taskTable() {
  const rows = [
    ["QE 环境容量不足", "环境检查", "P1", "待处理"],
    ["资产入库审批", "资产管理", "P2", "待审批"],
    ["GitLab Key 轮换", "凭据管理", "P2", "执行中"],
    ["流程失败复核", "运维流程", "P1", "待复核"],
  ];
  return `<table class="task-table"><thead><tr>${["任务", "来源", "优先级", "状态"].map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
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
