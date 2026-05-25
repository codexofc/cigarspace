// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Arthur Michon
// See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuthStore } from "@/stores/auth";
import { authApi } from "@/lib/queries";

/**
 * Wraps protected routes. On first mount, if we don't have an access token
 * (e.g. page refresh), tries one /auth/refresh round-trip silently before
 * deciding whether to redirect to /login.
 */
export function RequireAuth({
  requireAdmin = false,
}: {
  requireAdmin?: boolean;
}) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const setAccess = useAuthStore((s) => s.setAccess);
  const setUser = useAuthStore((s) => s.setUser);
  const location = useLocation();
  const [tried, setTried] = useState<boolean>(!!accessToken);

  useEffect(() => {
    if (accessToken) {
      setTried(true);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const tokens = await authApi.refresh();
        if (cancelled) return;
        setAccess({
          token: tokens.access_token,
          expiresIn: tokens.expires_in,
          scopes: tokens.scope.split(" ").filter(Boolean),
        });
        const me = await authApi.me();
        if (cancelled) return;
        setUser(me);
      } catch {
        /* no refresh cookie / expired → user stays unauthenticated */
      } finally {
        if (!cancelled) setTried(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken, setAccess, setUser]);

  if (!tried) {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }
  if (!accessToken) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (requireAdmin && !isAdmin) {
    return <Navigate to="/" replace />;
  }
  // touch user to satisfy "noUnusedLocals" linting when admin gate is off
  void user;
  return <Outlet />;
}
