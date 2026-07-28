import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { UploadDropzone } from "../src/components/UploadDropzone";

describe("UploadDropzone", () => {
  it("renders idle CTA and max size copy", () => {
    render(
      <MemoryRouter>
        <UploadDropzone
          state={{ kind: "idle" }}
          uploadKind="chapter"
          onFile={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Drop a chapter JSON here/i)).toBeInTheDocument();
    expect(screen.getByText(/max 50 MB/i)).toBeInTheDocument();
  });

  it("shows invalid_extension error frame", () => {
    render(
      <UploadDropzone
        state={{
          kind: "error",
          code: "invalid_extension",
          message: "bad",
          filename: "notes.pdf",
        }}
        uploadKind="chapter"
        onFile={() => undefined}
      />,
    );
    expect(screen.getByText(/Wrong file type/i)).toBeInTheDocument();
    expect(screen.getByText(/invalid_extension/i)).toBeInTheDocument();
  });

  it("invokes onFile when choosing a file", async () => {
    const user = userEvent.setup();
    const onFile = vi.fn();
    const { container } = render(
      <UploadDropzone state={{ kind: "idle" }} uploadKind="book" onFile={onFile} />,
    );
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["{}"], "chapter.json", { type: "application/json" });
    await user.upload(input, file);
    expect(onFile).toHaveBeenCalledTimes(1);
    expect(onFile.mock.calls[0][0].name).toBe("chapter.json");
  });
});
