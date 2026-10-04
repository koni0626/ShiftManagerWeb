import { test, expect, type Page } from "@playwright/test";
import { readFileSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";
const accounts = JSON.parse(
  readFileSync(resolve("../.local/demo-accounts.json"), "utf8"),
);
const screenshots = resolve("../deliverables");
mkdirSync(screenshots, { recursive: true });
async function login(page: Page, role: string) {
  await page.goto("/");
  await page.getByLabel("ログインID", { exact: true }).fill(role);
  await page
    .getByLabel("パスワード", { exact: true })
    .fill(accounts[role].password);
  await page.getByRole("button", { name: "ログイン", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "ログアウト", exact: true }),
  ).toBeVisible();
}

test("owner schedule, master input, map and responsive layout", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await login(page, "owner");
  await expect(
    page.getByRole("heading", { name: "訪問予定", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".week-table")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  const originCell = page
    .locator(".week-table tbody tr")
    .first()
    .locator("td")
    .first();
  const targetCell = page
    .locator(".week-table tbody tr")
    .nth(1)
    .locator("td")
    .nth(1);
  const moving = originCell.locator(".visit-card.draft").first();
  const visitId = await moving.getAttribute("data-visit-id");
  await moving.dragTo(targetCell);
  await expect(
    targetCell.locator(`[data-visit-id="${visitId}"]`),
  ).toBeVisible();
  await targetCell.locator(`[data-visit-id="${visitId}"]`).dragTo(originCell);
  await expect(
    originCell.locator(`[data-visit-id="${visitId}"]`),
  ).toBeVisible();
  await page.screenshot({ path: resolve(screenshots, "web-owner.png") });
  await page
    .getByRole("button", { name: "スタッフ・メンバー", exact: true })
    .click();
  await page
    .getByRole("button", { name: "スタッフを追加", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  const labels = page.locator(".choices label");
  for (let i = 0; i < (await labels.count()); i++) {
    const rect = await labels.nth(i).boundingBox();
    expect(rect!.height).toBeLessThan(90);
  }
  await page.getByLabel("名前", { exact: true }).fill("画面検証用スタッフ");
  await page.screenshot({ path: resolve(screenshots, "web-staff-form.png") });
  await page
    .getByRole("button", { name: "閉じる", exact: true })
    .last()
    .click();
  await page.getByRole("button", { name: "訪問先の地図", exact: true }).click();
  await expect(page.locator(".leaflet-container")).toBeVisible();
  await page
    .locator(".map-client")
    .first()
    .getByRole("button", { name: "位置を設定" })
    .click();
  await page.getByLabel("緯度", { exact: true }).fill("35.680000");
  await page.getByLabel("経度", { exact: true }).fill("139.750000");
  expect(
    await page
      .getByLabel("緯度", { exact: true })
      .evaluate((e: HTMLInputElement) => e.checkValidity()),
  ).toBe(true);
  await page
    .getByRole("button", { name: "閉じる", exact: true })
    .last()
    .click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".sidebar")).not.toBeInViewport();
  await expect(page.locator("body")).toHaveJSProperty("scrollWidth", 390);
  await page.screenshot({
    path: resolve(screenshots, "web-mobile-owner.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("member can read own visits and edit requests on mobile", async ({
  page,
}) => {
  await login(page, "member");
  await expect(
    page.getByRole("heading", { name: "今日の予定", exact: true }),
  ).toBeVisible();
  await expect(
    page.locator(".member-visits .person-card").first(),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".sidebar")).not.toBeInViewport();
  await page.screenshot({
    path: resolve(screenshots, "web-mobile-member.png"),
    fullPage: true,
  });
  await page
    .locator(".bottom-nav")
    .getByRole("button", { name: "勤務希望" })
    .click();
  await expect(page.locator(".request-day")).toHaveCount(31);
  await expect(page.locator("body")).toHaveJSProperty("scrollWidth", 390);
  await page.locator(".request-day select").first().selectOption("available");
  await expect(
    page.getByRole("button", { name: "勤務希望を提出", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "下書きを保存", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "勤務希望を提出", exact: true }),
  ).toBeEnabled();
  await page.screenshot({
    path: resolve(screenshots, "web-mobile-requests.png"),
    fullPage: true,
  });
});

test("admin can select a workspace", async ({ page }) => {
  await login(page, "admin");
  await expect(
    page.getByRole("heading", { name: "会社とオーナー", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "こもれびケア", exact: true }).click();
  await expect(page.locator(".week-table")).toBeVisible();
});
