// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Arthur Michon
// See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
/**
 * Thin fetch wrapper:
 * - injects the access bearer from the auth store,
 * - intercepts 401 → POST /auth/refresh (cookie-based) → retry once,
 * - throws ApiError on non-2xx with the RFC 7807 body if present.
 */

import { useAuthStore } from "@/stores/auth";

export interface ApiErrorBody {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
  request_id?: string;
  errors?: Array<{ field: string; message: string; code?: string | null }>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly body: ApiErrorBody | null;

  constructor(status: number, body: ApiErrorBody | null, message?: string) {
    super(message ?? body?.detail ?? body?.title ?? `HTTP ${status}`);
    this.status = status;
    this.body = body;
  }
}

const API_BASE = "/api/v1";

let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (isRefreshing && refreshPromise) {
    return refreshPromise;
  }
  isRefreshing = true;
  refreshPromise = (async () => {
    try {
      const resp = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
      if (!resp.ok) return false;
      const data = (await resp.json()) as {
        access_token: string;
        expires_in: number;
        scope: string;
      };
      useAuthStore.getState().setAccess({
        token: data.access_token,
        expiresIn: data.expires_in,
        scopes: data.scope.split(" ").filter(Boolean),
      });
      return true;
    } catch {
      return false;
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

export interface ApiRequestInit extends RequestInit {
  /** Set to true to skip the 401-refresh-retry dance (used by /auth itself). */
  skipAuth?: boolean;
  /** JSON body shortcut. */
  json?: unknown;
  /** Query params merged into the URL. */
  params?: Record<
    string,
    string | number | boolean | null | undefined | string[]
  >;
}

function buildUrl(path: string, params?: ApiRequestInit["params"]): string {
  let url = path.startsWith("http")
    ? path
    : `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  if (params) {
    const usp = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v === null || v === undefined || v === "") continue;
      if (Array.isArray(v)) {
        for (const item of v) usp.append(k, String(item));
      } else {
        usp.append(k, String(v));
      }
    }
    const qs = usp.toString();
    if (qs) url += (url.includes("?") ? "&" : "?") + qs;
  }
  return url;
}

export async function apiRequest<T>(
  path: string,
  init: ApiRequestInit = {},
): Promise<T> {
  const { skipAuth = false, json, params, ...rest } = init;
  const headers = new Headers(rest.headers);
  if (json !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!skipAuth) {
    const access = useAuthStore.getState().accessToken;
    if (access) headers.set("Authorization", `Bearer ${access}`);
  }
  const url = buildUrl(path, params);
  const body = json !== undefined ? JSON.stringify(json) : rest.body;

  const doRequest = (): Promise<Response> =>
    fetch(url, {
      ...rest,
      headers,
      body,
      credentials: "include",
    });

  let resp = await doRequest();
  if (resp.status === 401 && !skipAuth) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      const access = useAuthStore.getState().accessToken;
      if (access) headers.set("Authorization", `Bearer ${access}`);
      resp = await doRequest();
    }
  }
  if (resp.status === 204 || resp.status === 304) {
    return undefined as T;
  }
  const text = await resp.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }
  if (!resp.ok) {
    throw new ApiError(resp.status, parsed as ApiErrorBody | null);
  }
  return parsed as T;
}

export const api = {
  get<T>(path: string, init?: ApiRequestInit) {
    return apiRequest<T>(path, { ...init, method: "GET" });
  },
  post<T>(path: string, init?: ApiRequestInit) {
    return apiRequest<T>(path, { ...init, method: "POST" });
  },
  patch<T>(path: string, init?: ApiRequestInit) {
    return apiRequest<T>(path, { ...init, method: "PATCH" });
  },
  delete<T>(path: string, init?: ApiRequestInit) {
    return apiRequest<T>(path, { ...init, method: "DELETE" });
  },
};
