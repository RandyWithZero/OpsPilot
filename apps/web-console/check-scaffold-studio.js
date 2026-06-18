const fs = require("node:fs");
const vm = require("node:vm");

function createNode() {
  return {
    innerHTML: "",
    textContent: "",
    value: "",
    classList: { add() {}, remove() {}, toggle() {} },
    addEventListener() {},
    focus() {},
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
  fetch() { throw new Error("fetch should not run in scaffold render check"); },
  setTimeout() {},
  clearTimeout,
  Date,
  Intl,
  FormData: class FormData {},
});

vm.runInContext(fs.readFileSync("apps/web-console/app.js", "utf8"), context, { filename: "app.js" });

vm.runInContext(`
state.route = "scaffold";
state.apiOnline = false;
state.user = "admin@opspilot.cn";
state.scaffoldRequests = [];
renderScaffoldStudio();
if (!content.innerHTML.includes("创建脚手架请求")) throw new Error("scaffold form missing");
if (!content.innerHTML.includes("暂无可预览请求")) throw new Error("scaffold empty state missing");
if (!content.innerHTML.includes("Responsive shell")) throw new Error("scaffold state cards missing");

state.scaffoldStatus = "loading";
renderScaffoldStudio();
if (!content.innerHTML.includes("skeleton-line")) throw new Error("scaffold loading state missing");

state.scaffoldStatus = "idle";
state.scaffoldError = "backend unavailable";
renderScaffoldStudio();
if (!content.innerHTML.includes("提交失败")) throw new Error("scaffold error state missing");

state.scaffoldError = "";
state.scaffoldRequests = [{
  id: "scf_test",
  name: "Smoke Scaffold",
  owner: "Frontend",
  target: "web-api-worker-ai",
  priority: "high",
  status: "draft",
  summary: "A complete frontend scaffold request.",
  acceptance: "Responsive, accessible, and testable.",
  created_at: "2026-06-18T12:12:37Z",
}];
renderScaffoldStudio();
if (!content.innerHTML.includes("Smoke Scaffold")) throw new Error("scaffold request row missing");
if (!content.innerHTML.includes("web.shell")) throw new Error("scaffold contract preview missing");
`, context);

console.log("scaffold studio check passed");
