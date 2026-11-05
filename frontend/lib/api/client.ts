import { ApiErrorResponse } from "@/types/common";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  errorCode: string;
  requestId: string;
  status: number;

  constructor(status: number, data: ApiErrorResponse) {
    super(data.detail || "An API error occurred");
    this.name = "ApiError";
    this.status = status;
    this.errorCode = data.error_code || "UNKNOWN_ERROR";
    this.requestId = data.request_id || "unknown";
  }
}

/**
 * Standard HTTP client wrapper for all backend requests.
 * Includes credentials (httpOnly cookies) by default.
 */
export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  const defaultHeaders: HeadersInit = {
    "Content-Type": "application/json",
  };

  const response = await fetch(url, {
    ...options,
    credentials: "include", // Essential: sends and accepts httpOnly cookies
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    let errorData: ApiErrorResponse;
    try {
      errorData = await response.json();
    } catch {
      errorData = {
        detail: response.statusText || "Request failed",
        error_code: `HTTP_${response.status}`,
        request_id: response.headers.get("X-Request-ID") || "unknown",
      };
    }
    throw new ApiError(response.status, errorData);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return null as T;
  }

  return response.json();
}

