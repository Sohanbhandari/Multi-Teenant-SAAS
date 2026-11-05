/**
 * Common TypeScript interfaces mirroring backend schemas.
 */

export type Role = "admin" | "teacher" | "student";

export type RecordStatus = "active" | "archived" | "deleted";

export interface ApiErrorResponse {
  detail: string;
  error_code: string;
  request_id: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface HealthResponse {
  status: string;
  environment: string;
  version: string;
  database: string;
}

