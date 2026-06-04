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

const context = vm.createContext({
  console,
  document,
  localStorage: { getItem() { return null; } },
  sessionStorage: { getItem() { return ""; }, setItem() {}, removeItem() {} },
  fetch() { throw new Error("fetch should not run in integration route check"); },
  setTimeout,
  clearTimeout,
  Date,
  Intl,
  URL,
  FormData,
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
    auditEvents: clone(seed.auditEvents),
    filters: {},
    detail: null,
  });

  for (const route of newRoutes) {
    state.route = route;
    render();
    if (!content.innerHTML.includes(resourceConfig(route).title)) throw new Error("route title missing: " + route);
  }

  state.route = "workflowRuns";
  state.filters = {};
  state.detail = null;
  render();
  if (!content.innerHTML.includes("运行状态复核入口")) throw new Error("workflow run page missing");
  if (!content.innerHTML.includes("人工控制节点") || !content.innerHTML.includes("不能自动跳过")) throw new Error("manual approval step guard missing");

  state.apiOnline = true;
  for (const route of newRoutes) {
    state[collections[route]] = [];
    state.route = route;
    state.filters = {};
    renderResource(route);
    if (!content.innerHTML.includes("基础服务暂无记录")) throw new Error("live empty state missing: " + route);
    if (content.innerHTML.includes("企业 GitLab 主通道") || content.innerHTML.includes("QA 夜间回归报告")) throw new Error("live empty route leaked mock data: " + route);
  }

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
