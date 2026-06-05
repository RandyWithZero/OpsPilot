const fs = require("node:fs");
const vm = require("node:vm");

function createNode() {
  return {
    innerHTML: "",
    textContent: "",
    value: "",
    classList: { add() {}, remove() {}, toggle() {} },
    addEventListener() {},
    querySelectorAll() { return []; },
    close() {},
    showModal() {},
  };
}

const nodes = new Map();
const document = {
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
  fetch() { throw new Error("fetch should not run in dashboard render check"); },
  setTimeout,
  clearTimeout,
  Date,
  Intl,
});

vm.runInContext(fs.readFileSync("apps/web-console/app.js", "utf8"), context, { filename: "app.js" });

vm.runInContext(`
state.apiOnline = true;
state.route = "dashboard";
state.users = [];
state.projects = [];
state.assets = [];
state.environments = [];
renderDashboard();
if (!content.innerHTML.includes("实时清单为空")) throw new Error("live empty state missing");
for (const value of ["智能运营中台", "自动化测试平台", "模型服务网关"]) {
  if (content.innerHTML.includes(value)) throw new Error("live empty dashboard leaked mock row: " + value);
}

state.apiOnline = false;
const offlineTable = overviewTable();
if (!offlineTable.includes("智能运营中台")) throw new Error("offline mock overview rows missing");
`, context);

console.log("live-empty dashboard check passed");
