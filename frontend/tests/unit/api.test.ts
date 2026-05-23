import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api } from "@/lib/api";

const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
});

afterEach(() => {
  vi.restoreAllMocks();
});

function mockResponse(data: unknown, status = 200) {
  mockFetch.mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    statusText: "OK",
    json: async () => data,
  });
}

describe("api.content.create", () => {
  it("returns data on success", async () => {
    const item = { id: "1", type: "link", status: "pending" };
    mockResponse({ data: item, error: null });

    const res = await api.content.create({ type: "link", raw_url: "https://example.com" });

    expect(res.error).toBeNull();
    expect(res.data).toEqual(item);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/content"),
      expect.objectContaining({ method: "POST" })
    );
  });

  it("returns error on 422", async () => {
    mockResponse({ data: null, error: { code: "VALIDATION_ERROR", message: "bad input" } }, 422);

    const res = await api.content.create({ type: "link" });

    expect(res.data).toBeNull();
    expect(res.error?.code).toBe("VALIDATION_ERROR");
  });

  it("returns NETWORK_ERROR on fetch failure", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Failed to fetch"));

    const res = await api.content.create({ type: "link", raw_url: "https://x.com" });

    expect(res.error?.code).toBe("NETWORK_ERROR");
  });
});

describe("api.content.list", () => {
  it("passes query params", async () => {
    mockResponse({ data: [], meta: { total: 0, page: 1, per_page: 20, pages: 0 }, error: null });

    await api.content.list({ type: "link", page: 2 });

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("type=link");
    expect(url).toContain("page=2");
  });
});

describe("api.content.delete", () => {
  it("handles 204 no-content", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 204,
      json: async () => { throw new Error("no body"); },
    });

    const res = await api.content.delete("abc");
    expect(res.error).toBeNull();
  });
});
