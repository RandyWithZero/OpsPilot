const { test, expect } = require("@playwright/test");

test("web console scaffold vertical slice", async ({ page }) => {
  await page.goto(process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173");
  await page.getByLabel("本地模拟 / 开发头模式").check();
  await page.getByLabel("密码").fill("local-dev-password");
  await page.getByRole("button", { name: "登录控制台" }).click();

  await page.getByRole("button", { name: /脚手架生成/ }).click();
  await expect(page.getByRole("heading", { name: "从需求到可执行垂直切片" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "创建脚手架请求" })).toBeVisible();

  await page.getByLabel("项目名称").fill("Playwright Smoke Scaffold");
  await page.getByLabel("负责人").fill("Frontend Engineer");
  await page.getByLabel("业务目标").fill("Build one polished AI development scaffold vertical slice.");
  await page.getByLabel("验收标准").fill("Responsive shell, form states, and smoke coverage are visible.");
  await page.getByRole("button", { name: "生成请求" }).click();

  await expect(page.getByText("Playwright Smoke Scaffold")).toBeVisible();
  await page.getByRole("button", { name: "错误态" }).click();
  await expect(page.getByText("提交失败")).toBeVisible();
});
