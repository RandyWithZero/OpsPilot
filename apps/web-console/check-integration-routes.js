const fs = require("node:fs");
const vm = require("node:vm");

const styles = fs.readFileSync("apps/web-console/styles.css", "utf8");

function assertStyle(selector, declarations) {
  const rule = new RegExp(`${selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\{([\\s\\S]*?)\\}`, "g");
  const blocks = [...styles.matchAll(rule)].map((match) => match[1]).join("\n");
  if (!blocks) throw new Error(`missing style selector: ${selector}`);
  for (const declaration of declarations) {
    if (!blocks.includes(declaration)) throw new Error(`missing ${declaration} on ${selector}`);
  }
}

assertStyle(".detail-grid", ["min-width: 0"]);
assertStyle(".detail-panel", ["overflow: hidden"]);
assertStyle(".kv", ["min-width: 0"]);
assertStyle(".kv dd", ["min-width: 0", "overflow-wrap: anywhere"]);
assertStyle(".link-list", ["min-width: 0"]);
assertStyle(".link-list li", ["min-width: 0", "overflow-wrap: anywhere"]);
assertStyle(".json-block", ["max-width: 100%", "white-space: pre-wrap", "overflow-wrap: anywhere"]);
assertStyle(".workflow-run-panel", ["min-width: 0"]);
assertStyle(".run-step", ["min-width: 0"]);
assertStyle(".gate-copy", ["overflow-wrap: anywhere"]);
assertStyle(".topology-tree", ["min-width: 0"]);
assertStyle(".environment-board", ["grid-template-columns: repeat(3, minmax(220px, 1fr))"]);
assertStyle(".runtime-board", ["grid-template-columns: repeat(auto-fit, minmax(260px, 1fr))"]);
assertStyle(".runtime-task", ["min-width: 0"]);
assertStyle(".mini-kv", ["grid-template-columns: 82px minmax(0, 1fr)", "min-width: 0"]);
assertStyle(".builder-mode .sidebar,\n.builder-mode .topbar", ["display: none"]);
assertStyle(".builder-shell", ["grid-template-columns: 220px minmax(520px, 1fr) 300px", "min-width: 0"]);
assertStyle(".workflow-canvas", ["overflow: auto"]);
assertStyle(".workflow-list-fallback", ["display: none"]);
assertStyle(".ops-grid,\n.run-layout", ["min-width: 0"]);
assertStyle(".run-step-list li", ["min-width: 0", "grid-template-columns: 34px minmax(0, 1fr)"]);

function createNode() {
  return {
    innerHTML: "",
    textContent: "",
    value: "",
    dataset: {},
    classList: { add() {}, remove() {}, toggle() {} },
    addEventListener() {},
    querySelector() { return createNode(); },
    querySelectorAll() { return []; },
    close() {},
    showModal() {},
  };
}

const nodes = new Map();
const document = {
  body: { classList: { toggle() {} } },
  querySelector(selector) {
    if (!nodes.has(selector)) nodes.set(selector, createNode());
    return nodes.get(selector);
  },
  querySelectorAll() { return []; },
  addEventListener() {},
};

const localStore = new Map();
const sessionStore = new Map();
const context = vm.createContext({
  console,
  document,
  localStorage: { getItem(key) { return localStore.get(key) || null; }, setItem(key, value) { localStore.set(key, String(value)); } },
  sessionStorage: { getItem(key) { return sessionStore.get(key) || ""; }, setItem(key, value) { sessionStore.set(key, String(value)); }, removeItem(key) { sessionStore.delete(key); } },
  fetch() { throw new Error("fetch should not run in integration route check"); },
  setTimeout,
  clearTimeout,
  Date,
  Intl,
  URL,
  FormData,
  Buffer,
});

vm.runInContext(fs.readFileSync("apps/web-console/app.js", "utf8"), context, { filename: "app.js" });

const result = vm.runInContext(`
(async () => {
  const newRoutes = ["gitlabProfiles", "vcsOperations", "vcsWebhooks", "files", "testCases", "testSuites", "testRuns", "reports", "qualityGates"];
  Object.assign(state, {
    apiOnline: false,
    users: clone(seed.users),
    projects: clone(seed.projects),
    assets: clone(seed.assets),
    environments: clone(seed.environments),
    gitlabProfiles: clone(seed.gitlabProfiles),
    gitlabRepositories: clone(seed.gitlabRepositories),
    vcsOperations: clone(seed.vcsOperations),
    vcsWebhooks: clone(seed.vcsWebhooks),
    files: clone(seed.files),
    fileGrants: {},
    uploadSessions: [],
    testCases: clone(seed.testCases),
    testSuites: clone(seed.testSuites),
    testRuns: clone(seed.testRuns),
    reports: clone(seed.reports),
    qualityGates: clone(seed.qualityGates),
    agents: clone(seed.agents),
    skills: clone(seed.skills),
    credentials: clone(seed.credentials).map((credential) => sanitizeCredential(credential)),
    modelProviders: clone(seed.modelProviders),
    workflows: clone(seed.workflows),
    workflowVersions: clone(seed.workflowVersions),
    workflowRuns: clone(seed.workflowRuns),
    runtimeTasks: clone(seed.runtimeTasks),
    auditEvents: clone(seed.auditEvents),
    filters: {},
    detail: null,
  });

  function makeToken(claims) {
    const json = JSON.stringify({ sub: "usr_admin", role: "Admin", session_id: "ses_test", exp: Math.floor(Date.now() / 1000) + 600, ...claims });
    return "opspilot.v1." + Buffer.from(json, "utf8").toString("base64url") + ".sig";
  }

  const issuedToken = makeToken({ sub: "usr_admin", role: "Admin", session_id: "ses_login" });
  const refreshedToken = makeToken({ sub: "usr_admin", role: "Admin", session_id: "ses_login", exp: Math.floor(Date.now() / 1000) + 1200 });
  let authCalls = [];
  fetch = async (path, init = {}) => {
    authCalls.push({ path, init });
    if (String(path).endsWith("/v1/auth/login")) return { ok: true, status: 201, json: async () => ({ access_token: issuedToken, access_token_expires_at: new Date(Date.now() + 120000).toISOString(), refresh_token: "refresh-login", refresh_token_expires_at: new Date(Date.now() + 3600000).toISOString(), token_type: "Bearer", session_id: "ses_login" }) };
    if (String(path).endsWith("/v1/auth/refresh")) return { ok: true, status: 200, json: async () => ({ access_token: refreshedToken, access_token_expires_at: new Date(Date.now() + 1200000).toISOString(), refresh_token: "refresh-rotated", refresh_token_expires_at: new Date(Date.now() + 3600000).toISOString(), token_type: "Bearer", session_id: "ses_login" }) };
    if (String(path).endsWith("/v1/auth/logout")) return { ok: true, status: 200, json: async () => ({ ok: true }) };
    return { ok: true, status: 200, json: async () => [] };
  };
  document.querySelector("#login-email").value = "admin@opspilot.cn";
  document.querySelector("#login-role").value = "Viewer";
  document.querySelector("#login-dev-mode").checked = false;
  await signIn({ preventDefault() {} });
  if (state.authMode !== "bearer" || state.role !== "Admin" || state.actorId !== "usr_admin" || state.accessToken !== issuedToken) throw new Error("login did not derive session from bearer token");
  if (!authCalls[0].init.body.includes('"role":"Viewer"') || authCalls[0].init.body.includes("refresh-login")) throw new Error("login request did not preserve role input or leaked token material");

  let capturedRequest = null;
  fetch = async (path, init = {}) => {
    capturedRequest = { path, init };
    return { ok: true, status: 200, json: async () => [] };
  };
  await apiGet("/v1/projects");
  if (capturedRequest.init.headers.Authorization !== "Bearer " + issuedToken) throw new Error("apiGet did not send bearer Authorization header");
  if (capturedRequest.init.headers["X-Actor-ID"] || capturedRequest.init.headers["X-Actor-Role"]) throw new Error("bearer apiGet also sent deprecated actor headers");

  state.accessTokenExpiresAt = new Date(Date.now() - 1000).toISOString();
  authCalls = [];
  fetch = async (path, init = {}) => {
    authCalls.push({ path, init });
    if (String(path).endsWith("/v1/auth/refresh")) return { ok: true, status: 200, json: async () => ({ access_token: refreshedToken, access_token_expires_at: new Date(Date.now() + 1200000).toISOString(), refresh_token: "refresh-rotated", refresh_token_expires_at: new Date(Date.now() + 3600000).toISOString(), token_type: "Bearer", session_id: "ses_login" }) };
    return { ok: true, status: 200, json: async () => [] };
  };
  await apiGet("/v1/projects");
  if (state.accessToken !== refreshedToken || state.refreshToken !== "refresh-rotated") throw new Error("refresh did not rotate access and refresh tokens");
  if (authCalls.at(-1).init.headers.Authorization !== "Bearer " + refreshedToken) throw new Error("apiGet did not retry with refreshed bearer token");

  await signOut();
  if (state.accessToken || state.refreshToken || state.user) throw new Error("logout did not clear session tokens");
  Object.assign(state, {
    apiOnline: false,
    users: clone(seed.users),
    projects: clone(seed.projects),
    assets: clone(seed.assets),
    environments: clone(seed.environments),
    gitlabProfiles: clone(seed.gitlabProfiles),
    gitlabRepositories: clone(seed.gitlabRepositories),
    vcsOperations: clone(seed.vcsOperations),
    vcsWebhooks: clone(seed.vcsWebhooks),
    files: clone(seed.files),
    fileContexts: clone(seed.fileContexts),
    fileGrants: {},
    uploadSessions: [],
    testCases: clone(seed.testCases),
    testSuites: clone(seed.testSuites),
    testRuns: clone(seed.testRuns),
    reports: clone(seed.reports),
    qualityGates: clone(seed.qualityGates),
    agents: clone(seed.agents),
    skills: clone(seed.skills),
    credentials: clone(seed.credentials).map((credential) => sanitizeCredential(credential)),
    modelProviders: clone(seed.modelProviders),
    workflows: clone(seed.workflows),
    workflowVersions: clone(seed.workflowVersions),
    workflowRuns: clone(seed.workflowRuns),
    runtimeTasks: clone(seed.runtimeTasks),
    auditEvents: clone(seed.auditEvents),
    filters: {},
    detail: null,
    authError: "",
  });

  state.role = "Admin";
  state.actorId = "admin-console";
  state.authMode = "dev_headers";
  if (!canRoute("credentials") || !can("create", { type: "identity" }) || !can("delete", { type: "projects" })) throw new Error("Admin role did not receive high-risk permissions");
  capturedRequest = null;
  fetch = async (path, init = {}) => {
    capturedRequest = { path, init };
    return { ok: true, status: 200, json: async () => ({ ok: true }) };
  };
  await apiRequest("POST", "/v1/files/file_mock/download-grants", {});
  if (capturedRequest.init.headers["X-Actor-ID"] !== "admin-console" || capturedRequest.init.headers["X-Actor-Role"] !== "Admin") throw new Error("apiRequest did not send Admin actor headers");

  state.role = "Operator";
  state.actorId = "operator-console";
  fetch = async (path, init = {}) => {
    capturedRequest = { path, init };
    return { ok: false, status: 403, json: async () => ({ error: "permission_denied" }) };
  };
  const credentialFallback = await apiGet("/v1/credentials", { permissionFallback: [] });
  if (!Array.isArray(credentialFallback) || credentialFallback.length) throw new Error("permission fallback did not preserve live-empty credentials for Operator");
  if (capturedRequest.init.headers["X-Actor-ID"] !== "operator-console" || capturedRequest.init.headers["X-Actor-Role"] !== "Operator") throw new Error("apiGet did not send Operator actor headers");
  if (canRoute("credentials")) throw new Error("Operator could access credentials route");
  if (can("create", { type: "gitlabProfiles" }) || can("create", { type: "agents" }) || can("create", { type: "skills" }) || can("create", { type: "modelProviders" })) throw new Error("Operator could create Admin control-plane resources");
  if (can("delete", { type: "projects" }) || can("status", { type: "projects", nextStatus: "archived" })) throw new Error("Operator could delete or archive high-risk resources");
  if (!can("link", { actionName: "create-download-grant" }) || !can("link", { actionName: "create-workflow-run" }) || !can("create", { type: "vcsOperations" })) throw new Error("Operator lost expected operate permissions");

  state.route = "credentials";
  renderNav();
  if (!document.querySelector("#nav").innerHTML.includes("受限")) throw new Error("permission-aware nav did not mark restricted credentials route");
  renderResource("credentials");
  if (!content.innerHTML.includes("权限不足") || !content.innerHTML.includes("无法访问模型 Key")) throw new Error("credentials route did not render Chinese permission-denied state");

  state.role = "Viewer";
  if (!can("open", { type: "files" }) || can("create", { type: "projects" }) || can("link", { actionName: "create-workflow-run" }) || can("edit", { type: "identity" })) throw new Error("Viewer permission matrix is incorrect");
  state.fileGrants = {};
  await handleFileAction("create-download-grant", "file_mock");
  if (Object.keys(state.fileGrants).length) throw new Error("Viewer direct file grant action mutated offline state");
  const beforeViewerRuns = state.workflowRuns.length;
  await createWorkflowRun("wfl_mock_release", true);
  if (state.workflowRuns.length !== beforeViewerRuns) throw new Error("Viewer direct workflow run action mutated offline state");
  const beforeProfiles = state.gitlabProfiles.length;
  await createGitLabProfile({ name: "Viewer GitLab", base_url: "https://gitlab.viewer.local", gitlab_secret: "viewer-secret" });
  if (state.gitlabProfiles.length !== beforeProfiles) throw new Error("Viewer direct GitLab profile action mutated offline state");

  for (const route of newRoutes) {
    state.role = "Admin";
    state.route = route;
    render();
    if (!content.innerHTML.includes(resourceConfig(route).title)) throw new Error("route title missing: " + route);
  }

  for (const route of ["assets", "environments", "reports"]) {
    state.role = "Admin";
    state.route = route;
    state.filters = {};
    state.detail = null;
    render();
  }
  state.route = "assets";
  render();
  if (!content.innerHTML.includes("资产层级与能力工作台") || !content.innerHTML.includes("资产层级浏览") || !content.innerHTML.includes("能力 / 标签筛选")) throw new Error("asset topology workbench missing");
  state.filters.capability = "cuda";
  renderAssetWorkbench();
  if (filteredRows("assets").some((asset) => !(asset.capabilities || []).includes("cuda"))) throw new Error("asset capability filter did not apply");

  state.filters = {};
  state.route = "environments";
  render();
  if (!content.innerHTML.includes("DEV / QA / QE 环境绑定") || !content.innerHTML.includes("端点和附件管理") || !content.innerHTML.includes("核心 QA")) throw new Error("environment workbench missing");

  state.filters = { project_id: "prj_mock_core" };
  state.route = "reports";
  render();
  if (!content.innerHTML.includes("测试运行、报告与质量门禁") || !content.innerHTML.includes("项目质量摘要") || !content.innerHTML.includes("QA 夜间回归报告")) throw new Error("test report workbench missing");

  state.fileContexts = {};
  state.files = [
    { id: "fil_live_asset", filename: "asset-live-evidence.log", content_type: "text/plain", size_bytes: 64, owner_id: "usr_mock_admin", status: "available" },
    { id: "fil_live_env", filename: "env-live-report.pdf", content_type: "application/pdf", size_bytes: 128, owner_id: "usr_mock_ops", status: "available" },
  ];
  state.assets = [
    { id: "ast_live_file_ids", category: "server", name: "live-api-asset", status: "available", owner_id: "usr_mock_admin", location: "live", capabilities: ["linux"], file_ids: ["fil_live_asset"] },
  ];
  state.environments = [
    { id: "env_live_file_ids", project_id: "prj_mock_core", name: "Live QA", type: "QA", status: "active", owner_id: "usr_mock_ops", member_ids: ["usr_mock_ops"], asset_ids: ["ast_live_file_ids"], file_ids: ["fil_live_env"], endpoints: [{ name: "api", url: "https://qa.live.local" }] },
  ];
  state.filters = {};
  renderAssetWorkbench();
  if (!content.innerHTML.includes("asset-live-evidence.log") || content.innerHTML.includes("env-live-report.pdf")) throw new Error("asset attachment projection did not prefer asset.file_ids");
  renderEnvironmentWorkbench();
  if (!content.innerHTML.includes("env-live-report.pdf") || content.innerHTML.includes("asset-live-evidence.log")) throw new Error("environment attachment projection did not prefer environment.file_ids");

  state.files = clone(seed.files);
  state.fileContexts = clone(seed.fileContexts);
  state.assets = clone(seed.assets);
  state.environments = clone(seed.environments);

  state.route = "workflowRuns";
  state.filters = {};
  state.detail = null;
  render();
  if (!content.innerHTML.includes("运行状态复核入口")) throw new Error("workflow run page missing");
  if (!content.innerHTML.includes("人工控制节点") || !content.innerHTML.includes("不能自动跳过")) throw new Error("manual approval step guard missing");
  if (!content.innerHTML.includes("Dispatch Queue / Runtime Tasks") || !content.innerHTML.includes("wrt_mock_release_1") || content.innerHTML.includes("attempt_token")) throw new Error("runtime task queue rendering or sanitization missing");

  state.apiOnline = true;
  for (const route of newRoutes) {
    state[collections[route]] = [];
    state.route = route;
    state.filters = {};
    renderResource(route);
    if (!content.innerHTML.includes("基础服务暂无记录")) throw new Error("live empty state missing: " + route);
    if (content.innerHTML.includes("企业 GitLab 主通道") || content.innerHTML.includes("QA 夜间回归报告")) throw new Error("live empty route leaked mock data: " + route);
  }

  state.assets = [];
  state.environments = [];
  state.reports = [];
  state.testCases = [];
  state.testSuites = [];
  state.testRuns = [];
  state.qualityGates = [];
  state.fileContexts = {};
  state.route = "assets";
  renderAssetWorkbench();
  if (!content.innerHTML.includes("基础服务暂无记录") || content.innerHTML.includes("上海工作站")) throw new Error("live empty asset workbench leaked mock data");
  state.route = "environments";
  renderEnvironmentWorkbench();
  if (!content.innerHTML.includes("基础服务暂无记录") || content.innerHTML.includes("核心 DEV")) throw new Error("live empty environment workbench leaked mock data");
  state.route = "reports";
  renderTestReportWorkbench();
  if (!content.innerHTML.includes("基础服务暂无记录") || content.innerHTML.includes("QA 夜间回归报告")) throw new Error("live empty report workbench leaked mock data");

  state.apiOnline = false;
  state.credentials = [];
  state.gitlabProfiles = [];
  state.gitlabRepositories = {};
  let rejectedSensitiveUrl = false;
  try {
    await createGitLabProfile({ name: "危险 GitLab", base_url: "https://oauth2:glpat-url-token@gitlab.example.com?private_token=query-secret", gitlab_secret: "glpat-form-secret", repository_selection: [] });
  } catch {
    rejectedSensitiveUrl = true;
  }
  if (!rejectedSensitiveUrl) throw new Error("token-bearing GitLab base URL was not rejected");
  let rejectedRepositoryUrl = false;
  try {
    repositorySelection("100,platform/opspilot,OpsPilot,https://gitlab.example.com/platform/opspilot?private_token=repo-secret");
  } catch {
    rejectedRepositoryUrl = true;
  }
  if (!rejectedRepositoryUrl) throw new Error("token-bearing repository URL was not rejected");
  if (JSON.stringify(state).includes("glpat-url-token") || JSON.stringify(state).includes("repo-secret")) throw new Error("sensitive GitLab URL material retained after rejection");

  await createGitLabProfile({ name: "离线 GitLab", base_url: "https://gitlab.local", gitlab_secret: "glpat-offline-raw-secret", repository_selection: [] });
  const credentialDump = JSON.stringify(state.credentials);
  if (credentialDump.includes("glpat-offline-raw-secret")) throw new Error("raw GitLab token retained in offline credential state");
  if (!state.gitlabProfiles[0]?.credential_ref_id) throw new Error("GitLab profile did not receive credential ref");

  state.files = [addLocal("files", { filename: "smoke.txt", content_type: "text/plain", size_bytes: 16, owner_id: "" })];
  const fileId = state.files[0].id;
  await handleFileAction("create-upload-grant", fileId);
  await handleFileAction("create-upload-session", fileId);
  await handleFileAction("complete-upload-session", fileId);
  await handleFileAction("create-download-grant", fileId);
  if (state.files[0].status !== "available") throw new Error("offline file did not become available");
  if (!state.fileGrants[fileId]?.upload || !state.fileGrants[fileId]?.download) throw new Error("offline file grants missing");
  if (latestUploadSession(fileId)?.status !== "completed") throw new Error("offline upload session not completed");

  state.fileGrants[fileId] = {
    upload: { file_id: fileId, method: "PUT", url: "https://storage.example/upload?signature=grant-secret", expires_in_seconds: 900 },
    download: { file_id: fileId, method: "GET", url: "https://storage.example/download?token=download-secret", expires_in_seconds: 900 },
  };
  const grantHtml = fileGrantSummary(fileId);
  if (grantHtml.includes("grant-secret") || grantHtml.includes("download-secret") || grantHtml.includes("storage.example")) throw new Error("file grant summary rendered bearer URL material");

  state.vcsWebhooks = [{ id: "whk_raw", provider: "gitlab", profile_id: "glp_local", event_type: "Push Hook", repository_id: "100", payload: { token: "raw-webhook-token", nested: { private_key: "raw-private-key", safe: "value" } }, status: "received" }];
  state.filters = {};
  state.query = "raw-private-key";
  if (filteredRows("vcsWebhooks").length) throw new Error("raw webhook private_key was searchable");
  const webhookDetails = detailPairs("vcsWebhooks", state.vcsWebhooks[0]).map(([, value]) => value).join(" ");
  const webhookRelationships = relationshipControls("vcsWebhooks", state.vcsWebhooks[0]);
  if (webhookDetails.includes("raw-private-key") || webhookRelationships.includes("raw-private-key") || webhookDetails.includes("raw-webhook-token") || webhookRelationships.includes("raw-webhook-token")) throw new Error("raw webhook payload rendered in detail");

  const longValue = "https://gitlab.example.com/platform/" + "nested/".repeat(40) + "repo?already=redacted";
  state.vcsOperations = [{ id: "vcs_long", profile_id: "glp_long", repository_id: "repo_long", operation_type: "open_merge_request", branch: longValue, result: { web_url: longValue, response: { commit: "a".repeat(260) } }, status: "completed" }];
  const vcsDetails = detailPairs("vcsOperations", state.vcsOperations[0]).map(([, value]) => value).join(" ");
  const vcsRelationships = relationshipControls("vcsOperations", state.vcsOperations[0]);
  if (!vcsDetails.includes("json-block") || !vcsRelationships.includes("json-block")) throw new Error("long VCS detail JSON is not rendered in contained blocks");

  state.route = "workflows";
  state.detail = { type: "workflows", id: "wfl_mock_release" };
  renderResource("workflows");
  if (!content.innerHTML.includes("执行控制") || !content.innerHTML.includes("步骤时间线")) throw new Error("workflow run execution panel missing");
  if (!content.innerHTML.includes("等待前置节点") || !content.innerHTML.includes("人工确认")) throw new Error("workflow predecessor gate copy missing");

  const beforeRuns = state.workflowRuns.length;
  await createWorkflowRun("wfl_mock_release", false);
  if (state.workflowRuns.length !== beforeRuns + 1) throw new Error("offline workflow run create did not append a run");
  let run = state.workflowRuns[0];
  if (run.status !== "created" || !run.steps?.every((step) => Array.isArray(step.predecessor_node_ids))) throw new Error("offline workflow run did not preserve created status and predecessor snapshots");
  await startWorkflowRun(run.id);
  run = state.workflowRuns.find((item) => item.id === run.id);
  const triggerStep = run.steps.find((step) => step.step_type === "trigger");
  const agentStep = run.steps.find((step) => step.step_type === "agent");
  const manualStep = run.steps.find((step) => step.step_type === "manual");
  const resultStep = run.steps.find((step) => step.step_type === "result");
  if (run.status !== "running" || triggerStep.status !== "completed") throw new Error("offline workflow run start did not activate run and complete trigger");
  let rejectedEarlyResult = false;
  try {
    await updateWorkflowStep(run.id, resultStep.id + "|completed");
  } catch {
    rejectedEarlyResult = true;
  }
  if (!rejectedEarlyResult) throw new Error("result step transitioned before predecessors were satisfied");
  await updateWorkflowStep(run.id, agentStep.id + "|completed");
  let rejectedManualSkip = false;
  try {
    await updateWorkflowStep(run.id, manualStep.id + "|skipped");
  } catch {
    rejectedManualSkip = true;
  }
  if (!rejectedManualSkip) throw new Error("manual workflow step allowed skipped transition");
  await updateWorkflowStep(run.id, manualStep.id + "|completed");
  await updateWorkflowStep(run.id, resultStep.id + "|completed");
  run = state.workflowRuns.find((item) => item.id === run.id);
  if (run.status !== "completed" || !resultStep.output) throw new Error("offline workflow run did not roll up to completed with step output");
  agentStep.output = {
    api_key: "sk-output-api-key",
    nested: {
      authorization: "Bearer output-authorization-token",
      token: "output-token-value",
      secret: "output-secret-value",
      password: "output-password-value",
      cookie: "sessionid=output-cookie-value; csrftoken=output-csrf-value",
      note: "authorization=Bearer inline-authorization-value token=inline-token-value secret=inline-secret-value password=inline-password-value Cookie: sessionid=inline-cookie-value; csrftoken=inline-csrf-value",
    },
  };
  agentStep.error = "request failed api_key=error-api-key authorization=Bearer error-authorization-token token=error-token-value secret=error-secret-value password=error-password-value Cookie: sessionid=error-cookie-value; csrftoken=error-csrf-value";
  const sensitiveTimelineHtml = workflowRunTimeline(run);
  const forbiddenTimelineValues = [
    "sk-output-api-key",
    "output-authorization-token",
    "output-token-value",
    "output-secret-value",
    "output-password-value",
    "output-cookie-value",
    "output-csrf-value",
    "inline-authorization-value",
    "inline-token-value",
    "inline-secret-value",
    "inline-password-value",
    "inline-cookie-value",
    "inline-csrf-value",
    "error-api-key",
    "error-authorization-token",
    "error-token-value",
    "error-secret-value",
    "error-password-value",
    "error-cookie-value",
    "error-csrf-value",
  ];
  if (forbiddenTimelineValues.some((value) => sensitiveTimelineHtml.includes(value))) throw new Error("workflow timeline leaked sensitive output/error values");
  if (!sensitiveTimelineHtml.includes("[REDACTED]")) throw new Error("workflow timeline did not show redacted markers for sensitive output/error");

  openWorkflowBuilder("wfl_mock_release");
  if (!content.innerHTML.includes("节点 Palette") || !content.innerHTML.includes("workflow-canvas") || !content.innerHTML.includes("移动端节点列表")) throw new Error("workflow builder shell missing MVP regions");
  addWorkflowNode("result");
  addWorkflowEdge("approval", state.workflowBuilder.draft.nodes.at(-1).id);
  state.workflowBuilder.draft.nodes[1].input = "读取测试报告并输出发布风险。";
  state.workflowBuilder.draft.nodes[1].failure_strategy = "stop";
  const validBuilder = validateWorkflowDraft(state.workflowBuilder.draft);
  if (validBuilder.errors.length) throw new Error("valid workflow builder draft produced errors: " + validBuilder.errors.map((item) => item.message).join(","));
  const payload = workflowVersionPayload(state.workflowBuilder.draft);
  if (!payload.nodes.length || !payload.edges.length || JSON.stringify(payload).includes('"x"') || JSON.stringify(payload).includes('"y"')) throw new Error("workflow builder payload does not match version nodes/edges contract");

  state.skills.push({ id: "skl_forbidden", name: "未授权 Skill", version: "1.0.0", runtime: "python", status: "active", capabilities: [] });
  state.workflowBuilder.draft.nodes[1].skill_id = "skl_forbidden";
  const invalidBinding = validateWorkflowDraft(state.workflowBuilder.draft);
  if (!invalidBinding.errors.some((item) => item.message.includes("Skill 不属于所选智能体"))) throw new Error("workflow builder did not catch invalid agent/Skill binding");
  state.workflowBuilder.draft.nodes[1].skill_id = "skl_mock_release";
  const beforeVersions = state.workflowVersions.wfl_mock_release.length;
  await saveWorkflowBuilderVersion();
  if (state.workflowVersions.wfl_mock_release.length !== beforeVersions + 1) throw new Error("offline workflow builder save did not append a version");
  const saved = state.workflowVersions.wfl_mock_release.at(-1);
  if (!saved.nodes.some((node) => node.type === "result") || !saved.edges.some((edge) => edge.to_node_id === saved.nodes.at(-1).id)) throw new Error("saved workflow builder version lost node/edge edits");

  state.workflowVersions.wfl_mock_release.push({
    id: "wfv_injection",
    workflow_id: "wfl_mock_release",
    version: "inj",
    status: "draft",
    nodes: [
      { id: "node1\\" autofocus onfocus=alert(2) x=\\"", type: "<img src=x onerror=alert(1)>", name: "恶意节点" },
      { id: "safe-node", type: "approval", name: "安全节点" },
    ],
    edges: [{ from_node_id: "node1\\" autofocus onfocus=alert(2) x=\\"", to_node_id: "safe-node" }],
  });
  state.workflows[0].active_version_id = "wfv_injection";
  openWorkflowBuilder("wfl_mock_release");
  if (content.innerHTML.includes("<img src=x") || content.innerHTML.includes("onfocus=alert")) throw new Error("unsafe saved workflow node type/id rendered into builder HTML");
  const injectedPayload = workflowVersionPayload(state.workflowBuilder.draft);
  if (JSON.stringify(injectedPayload).includes("onfocus=alert") || !injectedPayload.nodes.every((node) => /^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(node.id))) throw new Error("unsafe workflow node ids were not normalized before save payload");
})()
`, context);

result.then(() => {
  console.log("integration route check passed");
}).catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
