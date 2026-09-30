import { expect, test } from "@playwright/test";

test("reviewer workflow: metrics, simulation, incident, analysis, and recovery", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
  await expect
    .poll(
      async () => {
        const response = await page.request.get("/api/metrics/summary");
        const data = await response.json();
        return data.services[0].metrics.request_count;
      },
      { timeout: 90000 },
    )
    .toBeGreaterThan(20);
  await page.getByRole("button", { name: "Admin login", exact: true }).click();
  await page
    .getByLabel("Password", { exact: true })
    .fill(process.env.ADMIN_PASSWORD || "ThemistoDemo2026!");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Admin access", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Simulate failure", exact: true }),
  ).toBeEnabled({ timeout: 150000 });
  await page
    .getByRole("button", { name: "Simulate failure", exact: true })
    .click();
  await expect(
    page
      .getByRole("link", { name: "Elevated HTTP errors", exact: true })
      .first(),
  ).toBeVisible({ timeout: 90000 });
  await page
    .getByRole("link", { name: "Elevated HTTP errors", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Triggering evidence" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Related logs" }),
  ).toBeVisible();
  await expect(
    page
      .getByText("simulated downstream dependency failure", { exact: false })
      .first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Analyze incident", exact: true })
    .click();
  await expect(page.getByText("Demo explanation", { exact: true })).toBeVisible(
    { timeout: 10000 },
  );
  await expect(
    page.getByRole("heading", { name: "Suggested troubleshooting steps" }),
  ).toBeVisible();
  await expect(page.locator(".badges .badge.resolved")).toBeVisible({
    timeout: 150000,
  });
  await page.screenshot({
    path: "test-results/incident-detail.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.reload();
  await expect(
    page.getByText("Demo explanation", { exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await expect(page.locator(".recharts-responsive-container")).toHaveCount(2);
  await expect(page.getByText("Loading incidents…")).toHaveCount(0);
  await page.screenshot({ path: "test-results/overview.png", fullPage: true });
});

test("public routes render on mobile without horizontal page overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of ["/", "/metrics", "/logs", "/incidents"]) {
    await page.goto(route);
    await expect(page.locator("h1")).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
  }
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
});
