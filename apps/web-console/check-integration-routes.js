const fs = require("node:fs");
const vm = require("node:vm");

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
    auditEvents: clone(seed.auditEvents),
    filters: {},
    detail: null,
  });

  for (const route of newRoutes) {
    state.route = route;
    render();
    if (!content.innerHTML.includes(resourceConfig(route).title)) throw new Error("route title missing: " + route);
  }

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
})()
`, context);

result.then(() => {
  console.log("integration route check passed");
}).catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
