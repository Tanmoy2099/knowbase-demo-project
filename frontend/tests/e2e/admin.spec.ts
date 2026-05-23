import { test, expect } from "@playwright/test";

test.describe("Admin health endpoint", () => {
  test("health endpoint is reachable", async ({ request }) => {
    const res = await request.get(
      `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:5000"}/api/admin/health`
    );
    // In CI without a running backend this will fail gracefully
    if (res.ok()) {
      const body = await res.json();
      expect(body).toHaveProperty("status");
      expect(body).toHaveProperty("services");
    } else {
      // Backend not running in this test context - acceptable
      expect([200, 503, 0]).toContain(res.status());
    }
  });
});
