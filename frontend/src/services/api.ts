import { HealthResponse, ApiErrorResponse } from '../types/api';

/**
 * Resolves the backend API base URL safely across environments.
 * When running in browser development on localhost / 127.0.0.1 and targeting local ports,
 * relative URL '' is used to route requests through Vite dev server's configured
 * proxy (/api -> http://127.0.0.1:8000). This eliminates cross-origin preflight overhead,
 * avoids Chromium Private Network Access (PNA) restrictions, and prevents localhost vs 127.0.0.1
 * origin mismatch failures ('Failed to fetch').
 */
export function getApiBaseUrl(): string {
  const configured = (import.meta.env.VITE_API_BASE_URL || '').trim();
  if (typeof window !== 'undefined') {
    if (!configured) {
      return '';
    }
    try {
      const parsed = new URL(configured, window.location.origin);
      const isLoopbackTarget =
        parsed.hostname === 'localhost' ||
        parsed.hostname === '127.0.0.1' ||
        parsed.hostname === '::1';
      const isLoopbackHost =
        window.location.hostname === 'localhost' ||
        window.location.hostname === '127.0.0.1' ||
        window.location.hostname === '::1';

      if (isLoopbackTarget && isLoopbackHost) {
        return '';
      }
    } catch {
      // Fallback to configured
    }
  }
  return configured;
}

export class ApiServiceError extends Error {
  code: string;
  details?: unknown;

  constructor(message: string, code = 'API_ERROR', details?: unknown) {
    super(message);
    this.name = 'ApiServiceError';
    this.code = code;
    this.details = details;
  }
}

/**
 * Perform a health check query against the backend API v1 probe.
 */
export async function fetchHealthStatus(): Promise<HealthResponse> {
  const url = `${getApiBaseUrl()}/api/v1/health`;
  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      let errorMessage = `Server returned HTTP ${response.status} (${response.statusText})`;
      let errorCode = `HTTP_${response.status}`;
      let errorDetails: unknown = undefined;

      try {
        const errorData = (await response.json()) as ApiErrorResponse;
        if (errorData?.error?.message) {
          errorMessage = errorData.error.message;
          errorCode = errorData.error.code || errorCode;
          errorDetails = errorData.error.details;
        }
      } catch {
        // Fallback to HTTP status text if body is not JSON
      }

      throw new ApiServiceError(errorMessage, errorCode, errorDetails);
    }

    const data = (await response.json()) as HealthResponse;
    return data;
  } catch (err: unknown) {
    if (err instanceof ApiServiceError) {
      throw err;
    }
    const rawMsg = err instanceof Error ? err.message : '';
    const friendlyMsg =
      rawMsg === 'Failed to fetch'
        ? 'Unable to connect to Orqestra backend. Verify server is running on http://127.0.0.1:8000.'
        : rawMsg || 'Failed to connect to Orqestra backend. Verify server is running.';
    throw new ApiServiceError(friendlyMsg, 'CONNECTION_ERROR');
  }
}

/**
 * Verify Supabase JWT token against backend /api/v1/auth/me and retrieve business memberships.
 */
export async function fetchAuthMe(token: string): Promise<import('../types/api').AuthContextResponse> {
  const url = `${getApiBaseUrl()}/api/v1/auth/me`;
  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status} ${response.statusText}`;
      let errorCode = `HTTP_${response.status}`;
      try {
        const errorData = (await response.json()) as ApiErrorResponse;
        if (errorData?.error?.message) {
          errorMessage = errorData.error.message;
          errorCode = errorData.error.code || errorCode;
        }
      } catch {
        // Fallback
      }
      throw new ApiServiceError(errorMessage, errorCode);
    }

    return (await response.json()) as import('../types/api').AuthContextResponse;
  } catch (err: unknown) {
    if (err instanceof ApiServiceError) throw err;
    const rawMsg = err instanceof Error ? err.message : '';
    const friendlyMsg =
      rawMsg === 'Failed to fetch'
        ? 'Unable to connect to authentication service. Please check backend connectivity.'
        : rawMsg || 'Authentication verification failed';
    throw new ApiServiceError(friendlyMsg, 'AUTH_ERROR');
  }
}

