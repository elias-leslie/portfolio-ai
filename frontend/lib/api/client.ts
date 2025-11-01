/**
 * Unified API client with retry logic and error handling
 */

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

/**
 * Custom API error class with status code
 */
export class ApiError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public response?: Response
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Sleep helper for retry backoff
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Unified API request function with retry logic and error handling
 *
 * @param url - Full URL or path (will be prefixed with API_BASE_URL if relative)
 * @param options - Fetch options
 * @param retries - Number of retry attempts (default: 3)
 * @returns Parsed JSON response
 * @throws ApiError on failure after retries
 */
export async function apiRequest<T>(
  url: string,
  options: RequestInit = {},
  retries = 3
): Promise<T> {
  // Construct full URL if relative path provided
  const fullUrl = url.startsWith("http") ? url : `${API_BASE_URL}${url}`;

  // Merge default headers with custom headers
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  // TODO: Add auth interceptor here when authentication is implemented
  // Example: headers["Authorization"] = `Bearer ${getAuthToken()}`;

  let lastError: Error | null = null;

  // Retry loop with exponential backoff
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const response = await fetch(fullUrl, {
        ...options,
        headers,
      });

      // Check for HTTP errors
      if (!response.ok) {
        // Try to extract error detail from response body
        let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        try {
          const errorData = await response.json();
          if (errorData.detail) {
            errorMessage = errorData.detail;
          }
        } catch {
          // If JSON parsing fails, use default error message
        }

        throw new ApiError(errorMessage, response.status, response);
      }

      // Parse and return successful response
      return (await response.json()) as T;
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      // Don't retry on client errors (4xx) - these won't succeed on retry
      if (error instanceof ApiError && error.statusCode >= 400 && error.statusCode < 500) {
        throw error;
      }

      // If we have retries left, wait before trying again
      if (attempt < retries - 1) {
        // Exponential backoff: 1s, 2s, 3s
        const backoffMs = (attempt + 1) * 1000;
        await sleep(backoffMs);
      }
    }
  }

  // All retries exhausted, throw last error
  throw lastError || new Error("Request failed after retries");
}

/**
 * Convenience method for GET requests
 */
export async function get<T>(url: string, options: RequestInit = {}): Promise<T> {
  return apiRequest<T>(url, { ...options, method: "GET" });
}

/**
 * Convenience method for POST requests
 */
export async function post<T>(
  url: string,
  data?: unknown,
  options: RequestInit = {}
): Promise<T> {
  return apiRequest<T>(url, {
    ...options,
    method: "POST",
    body: data ? JSON.stringify(data) : undefined,
  });
}

/**
 * Convenience method for PATCH requests
 */
export async function patch<T>(
  url: string,
  data?: unknown,
  options: RequestInit = {}
): Promise<T> {
  return apiRequest<T>(url, {
    ...options,
    method: "PATCH",
    body: data ? JSON.stringify(data) : undefined,
  });
}

/**
 * Convenience method for DELETE requests
 */
export async function del<T>(url: string, options: RequestInit = {}): Promise<T> {
  return apiRequest<T>(url, { ...options, method: "DELETE" });
}
