import { test, expect, type Page } from "@playwright/test";
import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import { readFileSync, mkdirSync } from "node:fs";
import { createServer } from "node:net";
import { resolve } from "node:path";

// These flows use atelier_test, never the user's development workspace.
const project = resolve("..");
const python = resolve(project, ".venv/Scripts/python.exe");
const backend = resolve(project, "backend");
const screenshots = resolve(project, "deliverables");
const password = "Atelier-test-password-123";
let server: ChildProcess;
let origin: string;
let logs = "";
const now = new Date();
const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
const day = `${month}-${String(now.getDate()).padStart(2, "0")}`;

test.beforeAll(async () => {
  mkdirSync(screenshots, { recursive: true });
  const socket = createServer();
  await new Promise<void>((r) => socket.listen(0, "127.0.0.1", r));
  const port = (socket.address() as { port: number }).port;
  await new Promise<void>((r, reject) =>
    socket.close((e) => (e ? reject(e) : r())),
  );
  origin = `http://127.0.0.1:${port}`;
  const credentials = JSON.parse(
    readFileSync(resolve(project, ".local/database.json"), "utf8"),
  );
  execFileSync(
    python,
    [
      "-c",
      "import sys; sys.path.insert(0, 'tests'); import conftest; conftest.migrate.__wrapped__()",
    ],
    { cwd: backend, windowsHide: true },
  );
  server = spawn(
    python,
    [
      "-m",
      "uvicorn",
      "app.main:app",
      "--host",
      "127.0.0.1",
      "--port",
      String(port),
    ],
    {
      cwd: backend,
      windowsHide: true,
      env: {
        ...process.env,
        DATABASE_URL: `postgresql+psycopg://atelier_app:${credentials.app}@127.0.0.1:55434/atelier_test`,
      },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  server.stdout?.on("data", (x) => {
    logs += x.toString();
  });
  server.stderr?.on("data", (x) => {
    logs += x.toString();
  });
  await expect
    .poll(async () => {
      if (server.exitCode !== null) throw new Error(logs);
      try {
        return (await fetch(origin + "/openapi.json")).status;
      } catch {
        return 0;
      }
    })
    .toBe(200);
});

test.afterAll(() => {
  server?.kill();
});

test.beforeEach(async ({ page }) => {
  execFileSync(
    python,
    [
      "-c",
      "import sys; sys.path.insert(0, 'tests'); import conftest; conftest.fixture.__wrapped__()",
    ],
    { cwd: backend, windowsHide: true },
  );
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const response = await route.fetch({
      url: origin + url.pathname + url.search,
    });
    await route.fulfill({ response });
  });
  await page.goto("/");
  await page.getByLabel("ログインID", { exact: true }).fill("owner-a");
  await page.getByLabel("パスワード", { exact: true }).fill(password);
  await page.getByRole("button", { name: "ログイン", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "自分の予定・希望", exact: true }),
  ).toBeVisible();
});

async function appApi(
  page: Page,
  path: string,
  method = "GET",
  body?: unknown,
) {
  return page.evaluate(
    async ({ path, method, body }) => {
      const csrf =
        document.cookie
          .split("; ")
          .find((x) => x.startsWith("atelier_csrf="))
          ?.split("=")[1] || "";
      const response = await fetch("/api/v1" + path, {
        method,
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": decodeURIComponent(csrf),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    },
    { path, method, body },
  );
}

test("owner creates own profile, saves own requests, and submits for a member", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page
    .getByRole("button", { name: "自分の予定・希望", exact: true })
    .click();
  await page
    .getByRole("button", { name: "自分のスタッフ情報を新規登録" })
    .click();
  await expect(page.getByLabel("名前", { exact: true })).toHaveValue("Owner a");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "保存する", exact: true })
    .click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(
    page.getByRole("button", { name: "自分の勤務希望", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel(`${day}の希望`, { exact: true })
    .selectOption("available");
  await page.getByLabel(`${day}の開始`, { exact: true }).fill("10:00");
  await page.getByRole("button", { name: "下書きを保存", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "勤務希望を提出", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "勤務希望を提出", exact: true })
    .click();
  await expect(page.getByText("提出済み", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "差し戻して編集", exact: true }),
  ).toBeEnabled();
  await page.screenshot({
    path: resolve(screenshots, "web-owner-personal.png"),
  });

  await page
    .getByRole("button", { name: "自分の訪問予定", exact: true })
    .click();
  await page
    .getByRole("button", { name: "自分の訪問予定を追加", exact: true })
    .click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("checkbox", { name: "Owner a", exact: true }),
  ).toBeChecked();
  await page.getByRole("dialog").getByLabel("閉じる", { exact: true }).click();
  await page.getByRole("button", { name: "勤務希望", exact: true }).click();
  const submission = page
    .locator(".submission")
    .filter({ has: page.getByText("Staff a", { exact: true }) });
  await submission
    .getByRole("button", { name: "代理入力", exact: true })
    .click();
  const modal = page.getByRole("dialog");
  await expect(modal.getByText("Staff a", { exact: true })).toBeVisible();
  await modal
    .getByLabel(`${day}の希望`, { exact: true })
    .selectOption("prefer_off");
  await modal
    .getByRole("button", { name: "下書きを保存", exact: true })
    .click();
  await expect(
    modal.getByRole("button", { name: "勤務希望を代理提出", exact: true }),
  ).toBeEnabled();
  await modal
    .getByRole("button", { name: "勤務希望を代理提出", exact: true })
    .click();
  await expect(modal.getByText("提出済み", { exact: true })).toBeVisible();
  await modal
    .getByLabel("差し戻し理由", { exact: true })
    .fill("電話で勤務時間の変更を受け付けたため");
  await modal
    .getByRole("button", { name: "差し戻して編集", exact: true })
    .click();
  await expect(modal.getByLabel(`${day}の希望`, { exact: true })).toBeEnabled();
  await modal
    .getByLabel(`${day}の希望`, { exact: true })
    .selectOption("available");
  await modal
    .getByRole("button", { name: "下書きを保存", exact: true })
    .click();
  await expect(
    modal.getByRole("button", { name: "勤務希望を代理提出", exact: true }),
  ).toBeEnabled();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("body")).toHaveJSProperty("scrollWidth", 390);
  await page.screenshot({
    path: resolve(screenshots, "web-mobile-proxy-requests.png"),
  });
  await modal.getByRole("button", { name: "閉じる", exact: true }).click();
  const actor = await appApi(page, "/auth/me");
  const data = await appApi(page, `/scopes/${actor.scope_id}/workspace`);
  const own = data.submissions.find((s: any) => s.staff_id === actor.staff_id);
  const other = data.submissions.find(
    (s: any) => s.staff_id !== actor.staff_id,
  );
  expect(own.days[0].start).toBe("10:00:00");
  expect(other.days[0].start).toBe("09:00:00");
  expect(
    data.history.some(
      (h: any) => h.action === "request_proxy" && h.actor_id === actor.id,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});

test("owner links existing staff and retains previously entered requests and visits", async ({
  page,
}) => {
  const actor = await appApi(page, "/auth/me");
  const root = `/scopes/${actor.scope_id}`;
  const data = await appApi(page, root + "/workspace");
  const staff = await appApi(page, root + "/staff", "POST", {
    name: "登録済みのオーナー",
    branch_ids: data.branches.map((b: any) => b.id),
    service_ids: [data.services[0].id],
  });
  await appApi(page, root + `/staff/${staff.id}/requests/${month}`, "PUT", {
    days: [{ date: day, kind: "available", start: "11:00", end: "17:00" }],
  });
  await appApi(page, root + "/visits", "POST", {
    ...Object.fromEntries(
      [
        "branch_id",
        "client_id",
        "service_id",
        "date",
        "start",
        "duration",
        "people",
      ].map((k) => [k, data.visits[0][k]]),
    ),
    staff_ids: [staff.id],
  });
  await page.reload();
  await page
    .getByRole("button", { name: "自分の予定・希望", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "自分のスタッフ情報を設定",
      exact: true,
    }),
  ).toBeVisible();
  await page.screenshot({
    path: resolve(screenshots, "web-owner-profile-link.png"),
  });
  await page
    .getByLabel("登録済みの自分のスタッフ情報", { exact: true })
    .selectOption(staff.id);
  await page
    .getByRole("button", { name: "選択したスタッフを自分に設定", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "登録済みのオーナー", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel(`${day}の開始`, { exact: true })).toHaveValue(
    "11:00",
  );
  await page
    .getByRole("button", { name: "自分の訪問予定", exact: true })
    .click();
  await expect(page.locator(".member-visits .person-card")).toHaveCount(1);
  await page
    .getByRole("button", { name: "スタッフ・メンバー", exact: true })
    .click();
  const card = page.locator(".person-card").filter({
    has: page.getByRole("heading", {
      name: "登録済みのオーナー",
      exact: true,
    }),
  });
  await expect(card.getByText("オーナー本人", { exact: true })).toBeVisible();
  await expect(
    card.getByRole("button", { name: "アカウントを停止", exact: true }),
  ).toHaveCount(0);
  expect((await appApi(page, "/auth/me")).role).toBe("owner");
});
