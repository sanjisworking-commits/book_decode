import type {
  ArgumentSpine,
  BookMetadata,
  ChapterListResponse,
  ProcessingStatus,
  SourceChapter,
} from "../types/api";
import { ApiError } from "../types/api";

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as {
      error?: { code?: string; message?: string; details?: Record<string, unknown> | null };
      detail?: string;
    };
    if (body.error) {
      return new ApiError(
        res.status,
        body.error.code ?? "unknown_error",
        body.error.message ?? res.statusText,
        body.error.details ?? null,
      );
    }
    return new ApiError(res.status, "unknown_error", body.detail ?? res.statusText);
  } catch {
    return new ApiError(res.status, "unknown_error", res.statusText);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    throw await parseError(res);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export async function uploadBook(file: File): Promise<BookMetadata> {
  const form = new FormData();
  form.append("file", file);
  return request<BookMetadata>("/books/upload", {
    method: "POST",
    body: form,
  });
}

export async function startProcessing(bookId: string): Promise<ProcessingStatus> {
  return request<ProcessingStatus>(`/books/${bookId}/process`, { method: "POST" });
}

export async function getStatus(bookId: string): Promise<ProcessingStatus> {
  return request<ProcessingStatus>(`/books/${bookId}/status`);
}

export async function getBook(bookId: string): Promise<BookMetadata> {
  return request<BookMetadata>(`/books/${bookId}`);
}

export async function listChapters(bookId: string): Promise<ChapterListResponse> {
  return request<ChapterListResponse>(`/books/${bookId}/chapters`);
}

export async function getChapterSpine(
  bookId: string,
  chapterId: string,
): Promise<ArgumentSpine> {
  return request<ArgumentSpine>(`/books/${bookId}/chapters/${chapterId}/spine`);
}

export async function getChapterSource(
  bookId: string,
  chapterId: string,
): Promise<SourceChapter> {
  return request<SourceChapter>(`/books/${bookId}/chapters/${chapterId}/source`);
}

export async function retryChapter(
  bookId: string,
  chapterId: string,
  force = false,
): Promise<ProcessingStatus> {
  const q = force ? "?force=true" : "";
  return request<ProcessingStatus>(
    `/books/${bookId}/chapters/${chapterId}/retry${q}`,
    { method: "POST" },
  );
}

export async function deleteBook(bookId: string): Promise<void> {
  return request<void>(`/books/${bookId}`, { method: "DELETE" });
}
