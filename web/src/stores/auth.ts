// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Arthur Michon
// See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
/**
 * Auth store — keeps the access token in memory (never localStorage), tracks
 * its expiry timestamp, and remembers the latest /me snapshot.
 *
 * The refresh token lives in the HttpOnly `cigars_refresh` cookie and is
 * therefore inaccessible to JS by design. Refresh attempts re-populate the
 * access state via the /auth/refresh roundtrip.
 */

import { create } from "zustand";

export interface CurrentUser {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_admin: boolean;
}

interface AuthState {
  accessToken: string | null;
  expiresAt: number | null; // epoch ms
  scopes: string[];
  user: CurrentUser | null;
  isAdmin: boolean;
  setAccess: (payload: {
    token: string;
    expiresIn: number;
    scopes: string[];
  }) => void;
  setUser: (user: CurrentUser | null) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  expiresAt: null,
  scopes: [],
  user: null,
  isAdmin: false,
  setAccess: ({ token, expiresIn, scopes }) =>
    set({
      accessToken: token,
      expiresAt: Date.now() + expiresIn * 1000,
      scopes,
      isAdmin: scopes.includes("admin"),
    }),
  setUser: (user) =>
    set((state) => ({
      user,
      isAdmin: user?.is_admin ?? state.isAdmin,
    })),
  clear: () =>
    set({
      accessToken: null,
      expiresAt: null,
      scopes: [],
      user: null,
      isAdmin: false,
    }),
}));
