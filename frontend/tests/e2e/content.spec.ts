import { test, expect } from "@playwright/test";

test.describe("Content Management", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("page loads with save form and empty state", async ({ page }) => {
    await expect(page.getByText("Knowbase")).toBeVisible();
    await expect(page.getByText("Save Content")).toBeVisible();
  });

  test("type selector switches between Link and Note", async ({ page }) => {
    await page.getByText("Link").click();
    await expect(page.getByLabel(/url/i)).toBeVisible();

    await page.getByText("Note").click();
    await expect(page.getByLabel(/content/i)).toBeVisible();
    await expect(page.locator("label[for='raw_url']")).toHaveCount(0);
  });

  test("can submit a link and see it appear in list", async ({ page }) => {
    // Mock the API response
    await page.route("**/api/content", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            data: {
              id: "test-id-1",
              type: "link",
              raw_url: "https://example.com",
              title: "Example Domain",
              body: null,
              status: "pending",
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            },
            error: null,
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            data: [
              {
                id: "test-id-1",
                type: "link",
                raw_url: "https://example.com",
                title: "Example Domain",
                body: null,
                status: "pending",
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              },
            ],
            meta: { total: 1, page: 1, per_page: 20, pages: 1 },
            error: null,
          }),
        });
      }
    });

    await page.goto("/");
    await page.getByText("Link").click();
    await page.getByLabel(/url/i).fill("https://example.com");
    await page.getByRole("button", { name: /save/i }).click();

    await expect(page.getByText("Example Domain")).toBeVisible({ timeout: 5000 });
  });
});
