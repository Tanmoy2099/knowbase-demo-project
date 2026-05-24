import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ContentSaveForm } from "@/components/ContentSaveForm";
import { api } from "@/lib/api";

vi.mock("@/lib/api");

describe("ContentSaveForm", () => {
  it("renders type selector and submit button", () => {
    render(<ContentSaveForm onSuccess={() => {}} />);
    expect(screen.getByText("Link")).toBeInTheDocument();
    expect(screen.getByText("YouTube")).toBeInTheDocument();
    expect(screen.getByText("Note")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
  });

  it("shows URL field for link type by default", () => {
    render(<ContentSaveForm onSuccess={() => {}} />);
    expect(screen.getByLabelText(/url/i)).toBeInTheDocument();
  });

  it("shows body textarea when Note is selected", async () => {
    const user = userEvent.setup();
    render(<ContentSaveForm onSuccess={() => {}} />);
    await user.click(screen.getByText("Note"));
    expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
  });

  it("calls api.content.create and triggers onSuccess", async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    vi.mocked(api.content.create).mockResolvedValueOnce({
      data: { id: "1", type: "link", status: "pending", raw_url: "https://x.com", title: null, body: null, extra_context: null, user_instructions: null, created_at: "", updated_at: "" },
      error: null,
    });

    render(<ContentSaveForm onSuccess={onSuccess} />);
    await user.type(screen.getByLabelText(/url/i), "https://example.com");
    await user.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce());
  });

  it("shows error message on API failure", async () => {
    const user = userEvent.setup();
    vi.mocked(api.content.create).mockResolvedValueOnce({
      data: null,
      error: { code: "VALIDATION_ERROR", message: "URL is required" },
    });

    render(<ContentSaveForm onSuccess={() => {}} />);
    await user.type(screen.getByLabelText(/url/i), "https://x.com");
    await user.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => expect(screen.getByText("URL is required")).toBeInTheDocument());
  });
});
