import { expect, test } from "@playwright/test";

test("驾驶舱和四个入口可用", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "今天，先看全局。" })).toBeVisible();
  await expect(page.getByText("Local · Read only")).toBeVisible();
  await page.getByRole("link", { name: "资料检索" }).click();
  await expect(page.getByRole("heading", { name: "资料检索" })).toBeVisible();
});

test("检索返回可点击证据", async ({ page }) => {
  await page.goto("/library");
  await page.getByPlaceholder("搜索公司、人物、框架、观点或数字…").fill("物理瓶颈");
  await page.getByRole("button", { name: "搜索" }).click();
  await expect(page.locator(".search-result").first()).toBeVisible();
  await page.locator(".search-result").first().click();
  await expect(page.getByText("本地原文预览")).toBeVisible();
});

test("未配置模型时智能体给出可恢复错误", async ({ page }) => {
  await page.goto("/ask");
  await page.getByPlaceholder(/例如/).fill("解释物理瓶颈论");
  await page.getByRole("button", { name: /开始研究/ }).click();
  await expect(page.getByText(/DEEPSEEK_API_KEY|仅本地可见/)).toBeVisible({ timeout: 30_000 });
});
