// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Arthur Michon
// See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
/**
 * Centralised TanStack Query keys + query functions hitting the FastAPI.
 * Centralising lets us invalidate from anywhere in the app with a single
 * import.
 */

import { api } from "./api-client";

// --- Auth ------------------------------------------------------------------

export interface LoginResponse {
  access_token: string;
  expires_in: number;
  scope: string;
}

export interface MeResponse {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_admin: boolean;
  last_login_at: string | null;
  created_at: string | null;
}

export const authApi = {
  login: (email: string, password: string) =>
    api.post<LoginResponse>("/auth/login", {
      json: { email, password },
      skipAuth: true,
    }),
  refresh: () => api.post<LoginResponse>("/auth/refresh", { skipAuth: true }),
  logout: () => api.post<void>("/auth/logout"),
  me: () => api.get<MeResponse>("/me"),
};

// --- Catalogue -------------------------------------------------------------

export interface Link {
  self: string;
  [k: string]: string | null | undefined;
}

export interface PageLinks {
  self: string;
  first: string;
  last: string;
  next: string | null;
  prev: string | null;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  _links: PageLinks;
}

export interface CigarSummary {
  id: string;
  slug: string;
  full_name: string;
  vitola_name: string;
  format_category: string;
  is_cuban: boolean;
  _links: Link;
}

export interface CigarDetail extends CigarSummary {
  line_id: string;
  length_mm: string | null;
  ring_gauge: number | null;
  ring_gauge_mm: string | null;
  weight_g: string | null;
  wrapper_country: string | null;
  binder_country: string | null;
  filler_countries: string[];
  strength: string | null;
  body: string | null;
  release_year: number | null;
  blend_components: Array<{
    component_type: string;
    tobacco_origin: string | null;
    tobacco_region: string | null;
    tobacco_variety: string | null;
    aging_years: number | null;
    percentage: string | null;
    source_confidence: string;
  }>;
  flavor_profile: Record<string, unknown>;
}

export interface CigarsListParams {
  page: number;
  page_size: number;
  brand?: string;
  format?: string;
  is_cuban?: boolean;
  country_origin?: string;
  strength?: string;
  sort?: string;
}

export const cigarsApi = {
  list: (params: CigarsListParams) =>
    api.get<Paginated<CigarSummary>>("/cigars", { params: { ...params } }),
  detail: (slug: string) => api.get<CigarDetail>(`/cigars/${slug}`),
  customsMatches: (slug: string) =>
    api.get<CustomsMatchResponse[]>(`/cigars/${slug}/customs-matches`),
  search: (q: string, limit = 20) =>
    api.get<SearchResponse>("/cigars/search", { params: { q, limit } }),
};

// --- Brands ----------------------------------------------------------------

export interface BrandResponse {
  id: string;
  slug: string;
  name: string;
  country_origin: string | null;
  parent_company: string | null;
  founded_year: number | null;
  is_active: boolean;
  aliases: string[];
  _links: Link;
}

export const brandsApi = {
  list: (page = 1, page_size = 100) =>
    api.get<Paginated<BrandResponse>>("/brands", {
      params: { page, page_size },
    }),
};

// --- Customs ---------------------------------------------------------------

export interface CustomsSource {
  id: string;
  code: string;
  country_code: string;
  display_name: string;
  is_active: boolean;
  last_checked_at: string | null;
  consecutive_failures: number;
  _links: Link;
}

export interface CustomsPublicationResponse {
  id: string;
  source_id: string;
  regulator_reference: string;
  publication_date: string | null;
  effective_date: string | null;
  status: string;
  entries_count: number;
  _links: Link;
}

export const customsApi = {
  sources: () =>
    api.get<Paginated<CustomsSource>>("/customs-sources", {
      params: { page: 1, page_size: 50 },
    }),
  publications: (code: string, page = 1, page_size = 20) =>
    api.get<Paginated<CustomsPublicationResponse>>(
      `/customs-sources/${code}/publications`,
      { params: { page, page_size } },
    ),
};

// --- Matches ---------------------------------------------------------------

export interface CustomsMatchResponse {
  id: string;
  cigar_id: string;
  customs_entry_id: string;
  match_method: string;
  score: string;
  confidence: string;
  status: string;
  pack_size_bucket: number | null;
  signals: Record<string, number>;
  matched_at: string;
  matched_by: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  notes: string | null;
  _links: Link;
}

export interface MatchesListParams {
  page: number;
  page_size: number;
  status?: string[];
}

export const matchesApi = {
  list: (params: MatchesListParams) =>
    api.get<Paginated<CustomsMatchResponse>>("/matches", {
      params: { ...params },
    }),
  detail: (id: string) => api.get<CustomsMatchResponse>(`/matches/${id}`),
  decide: (
    id: string,
    status: "human_accepted" | "human_rejected",
    notes?: string,
  ) =>
    api.patch<CustomsMatchResponse>(`/matches/${id}`, {
      json: { status, notes: notes ?? null },
    }),
};

// --- Search ----------------------------------------------------------------

export interface SearchHit {
  cigar: CigarSummary;
  score: number;
  matched_by: string[];
}

export interface SearchResponse {
  query: string;
  items: SearchHit[];
  total: number;
}

// --- Admin jobs ------------------------------------------------------------

export interface JobAcceptedResponse {
  job_id: string;
  status: string;
  _links: Link;
}

export const adminApi = {
  refreshCustomsSource: (code: string) =>
    api.post<JobAcceptedResponse>(`/customs-sources/${code}/refresh-jobs`),
  rerunMatchingAll: () =>
    api.post<JobAcceptedResponse>("/match-jobs", { json: { scope: "all" } }),
  rerunMatchingForCigar: (cigarId: string) =>
    api.post<JobAcceptedResponse>("/match-jobs", {
      json: { scope: "cigar", cigar_id: cigarId },
    }),
};

// --- System ----------------------------------------------------------------

export interface HealthResponse {
  status: "ok" | "degraded" | "down";
  checks: Array<{
    name: string;
    status: "ok" | "degraded" | "down";
    detail?: string | null;
  }>;
}

export interface VersionResponse {
  version: string;
  git_sha: string | null;
  schema_head: string | null;
}

export const systemApi = {
  health: () => api.get<HealthResponse>("/health"),
  version: () => api.get<VersionResponse>("/version"),
};

// --- Query keys (for invalidation) -----------------------------------------

export const qk = {
  me: ["me"] as const,
  cigars: (params?: Partial<CigarsListParams>) => ["cigars", params] as const,
  cigar: (slug: string) => ["cigar", slug] as const,
  cigarMatches: (slug: string) => ["cigar-matches", slug] as const,
  search: (q: string) => ["search", q] as const,
  brands: ["brands"] as const,
  customsSources: ["customs-sources"] as const,
  matches: (params?: Partial<MatchesListParams>) =>
    ["matches", params] as const,
  match: (id: string) => ["match", id] as const,
  health: ["health"] as const,
  version: ["version"] as const,
};
