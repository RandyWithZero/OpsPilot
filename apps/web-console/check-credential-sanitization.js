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

const context = vm.createContext({
  console,
  document,
  localStorage: { getItem() { return null; } },
  sessionStorage: { getItem() { return ""; }, setItem() {}, removeItem() {} },
  fetch() { throw new Error("fetch should not run in credential sanitization check"); },
  setTimeout,
  clearTimeout,
  Date,
  Intl,
});

vm.runInContext(fs.readFileSync("apps/web-console/app.js", "utf8"), context, { filename: "app.js" });

vm.runInContext(`
state.apiOnline = false;
state.filters = {};
state.credentials = [
  { id: "crd_local_existing", provider: "model_provider", name: "Existing Key", secret_ref: "vault://local/existing", secret_fingerprint: "fp_old", status: "active" },
];

applyLocal("credentials", "crd_local_existing", (item) => ({
  ...item,
  name: "Rotated Key",
  secret: "offline-rotate-secret",
  updated_at: new Date().toISOString(),
}));

applyLocal("credentials", null, () => ({
  id: "crd_local_created",
  provider: "model_provider",
  name: "Created Key",
  secret: "offline-create-secret",
  status: "active",
}));

const serializedCredentials = JSON.stringify(state.credentials);
for (const rawSecret of ["offline-rotate-secret", "offline-create-secret"]) {
  if (serializedCredentials.includes(rawSecret)) throw new Error("raw secret retained in state.credentials: " + rawSecret);
  state.query = rawSecret;
  if (filteredRows("credentials").length) throw new Error("raw secret matched credential search: " + rawSecret);
}

for (const credential of state.credentials) {
  if ("secret" in credential) throw new Error("credential retained secret property: " + credential.id);
  if (!credential.secret_ref) throw new Error("credential missing secret ref: " + credential.id);
  if (!credential.secret_fingerprint) throw new Error("credential missing secret fingerprint: " + credential.id);
}
`, context);

console.log("credential sanitization check passed");
