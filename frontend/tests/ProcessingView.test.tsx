import { describe, expect, it } from "vitest";
import { ProcessingView } from "../src/components/ProcessingView";
import { render, screen } from "@testing-library/react";
import type { ProcessingStatus } from "../src/types/api";

const base: ProcessingStatus = {
  schema_version: "1.0",
  book_id: "b1",
  job_id: "j1",
  processing_status: "analysing_chapters",
  current_stage: "analysing_chapters",
  stage_index: 5,
  stages_total: 10,
  chapter_count: 2,
  processed_chapter_count: 1,
  failed_chapter_count: 0,
  current_chapter_id: "ch02",
  partial_success: false,
  error: null,
  updated_at: null,
  chapters: [
    {
      chapter_id: "ch01",
      title: "One",
      chapter_number: 1,
      status: "completed",
      retry_count: 0,
      error: null,
    },
    {
      chapter_id: "ch02",
      title: "Two",
      chapter_number: 2,
      status: "extracting",
      retry_count: 0,
      error: null,
    },
  ],
};

describe("ProcessingView", () => {
  it("shows progressive unlock copy when a chapter is already ready", () => {
    render(<ProcessingView status={base} />);
    expect(screen.getByText(/First chapters ready/i)).toBeInTheDocument();
    expect(screen.getByText(/you can open the first/i)).toBeInTheDocument();
    expect(screen.getByText(/Analysing chapters/i)).toBeInTheDocument();
    expect(screen.getByText("One")).toBeInTheDocument();
    expect(screen.getByText("Two")).toBeInTheDocument();
  });

  it("shows waiting-on-model copy when LLM call is in flight", () => {
    render(
      <ProcessingView
        status={{
          ...base,
          processed_chapter_count: 0,
          current_chapter_id: "ch01",
          chapters: [
            {
              chapter_id: "ch01",
              title: "One",
              chapter_number: 1,
              status: "extracting",
              retry_count: 0,
              error: null,
              progress: "chunk 1/1",
            },
          ],
        }}
        elapsedLabel="1m 12s"
        waitingOnLlm
      />,
    );
    expect(screen.getByText(/Waiting on the model/i)).toBeInTheDocument();
    expect(screen.getAllByText(/chunk 1\/1/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Decoding · 1m 12s/i)).toBeInTheDocument();
  });

  it("shows book ready heading when completed", () => {
    render(
      <ProcessingView
        status={{
          ...base,
          processing_status: "completed",
          stage_index: 10,
          processed_chapter_count: 2,
        }}
      />,
    );
    expect(screen.getByRole("heading", { name: /Book ready/i })).toBeInTheDocument();
  });

  it("shows failure copy with error code", () => {
    render(
      <ProcessingView
        status={{
          ...base,
          processing_status: "failed",
          chapters: [
            {
              chapter_id: "ch01",
              title: "One",
              chapter_number: 1,
              status: "failed",
              retry_count: 0,
              error: {
                code: "extraction_failed",
                message: "Anthropic HTTP 401: invalid x-api-key",
              },
            },
          ],
          error: {
            code: "extraction_failed",
            message:
              "All chapters failed Argument Spine extraction. First error: Anthropic HTTP 401: invalid x-api-key",
          },
        }}
      />,
    );
    expect(screen.getByText(/Couldn’t decode this book/i)).toBeInTheDocument();
    expect(screen.getByText(/extraction_failed/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Anthropic HTTP 401/i).length).toBeGreaterThan(0);
  });
});
