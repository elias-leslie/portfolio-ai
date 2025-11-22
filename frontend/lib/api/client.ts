/**
 * Unified API client with retry logic and error handling
 */

/**
 * Get the correct API base URL based on how the user is accessing the site.
 * - Tailscale (100.123.190.81:3000) → Use Tailscale backend (100.123.190.81:8000)
 * - Local network (192.168.8.233:3000) → Use local backend (192.168.8.233:8000)
 * - Localhost → Use localhost:8000
 */
let cachedApiBaseUrl: string | null = null;

function getApiBaseUrl(): string {
  // Return cached value if already computed
  if (cachedApiBaseUrl) {
    return cachedApiBaseUrl;
  }

  // Server-side rendering: use environment variable
  if (typeof window === "undefined") {
    return process.env.NEXT_PUBLIC_API_URL || "http://192.168.8.233:8000";
  }

  // Client-side: detect based on current hostname
  const hostname = window.location.hostname;
  const port = 8000; // Backend always on port 8000

  let baseUrl: string;

  // Tailscale access
  if (hostname === "100.123.190.81") {
    baseUrl = `http://100.123.190.81:${port}`;
  }
  // Local network access
  else if (hostname === "192.168.8.233") {
    baseUrl = `http://192.168.8.233:${port}`;
  }
  // Localhost/127.0.0.1
  else if (hostname === "localhost" || hostname === "127.0.0.1") {
    baseUrl = `http://localhost:${port}`;
  }
  // Fallback to environment variable or local network
  else {
    baseUrl = process.env.NEXT_PUBLIC_API_URL || `http://${hostname}:${port}`;
  }

  // Cache for subsequent calls
  cachedApiBaseUrl = baseUrl;
  return baseUrl;
}

/**
 * Export the API base URL (for debugging/logging purposes)
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
 * @param url - Full URL or path (will be prefixed with detected API base URL if relative)
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
  // Use getApiBaseUrl() to detect the correct backend based on current access method
  const fullUrl = url.startsWith("http") ? url : `${getApiBaseUrl()}${url}`;

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
