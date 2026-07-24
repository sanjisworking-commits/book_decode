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
  it("shows mid-pipeline stage list and chapter grid", () => {
    render(<ProcessingView status={base} />);
    expect(screen.getByText(/Working through your book/i)).toBeInTheDocument();
    expect(screen.getByText(/Analysing chapters/i)).toBeInTheDocument();
    expect(screen.getByText("One")).toBeInTheDocument();
    expect(screen.getByText("Two")).toBeInTheDocument();
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
          chapters: [],
          error: { code: "structure_unreadable", message: "Bad structure" },
        }}
      />,
    );
    expect(screen.getByText(/Couldn’t decode this book/i)).toBeInTheDocument();
    expect(screen.getByText(/structure_unreadable/i)).toBeInTheDocument();
  });
});
