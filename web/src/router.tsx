// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Arthur Michon
// See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
import { createBrowserRouter, Navigate } from "react-router-dom";
import { LoginPage } from "@/pages/Login";
import { DashboardPage } from "@/pages/Dashboard";
import { CigarsListPage } from "@/pages/CigarsList";
import { CigarDetailPage } from "@/pages/CigarDetail";
import { MatchesPendingPage } from "@/pages/MatchesPending";
import { MePage } from "@/pages/Me";
import { AppLayout } from "@/components/layout/AppLayout";
import { RequireAuth } from "@/components/layout/RequireAuth";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <DashboardPage /> },
          { path: "cigars", element: <CigarsListPage /> },
          { path: "cigars/:slug", element: <CigarDetailPage /> },
          { path: "me", element: <MePage /> },
        ],
      },
    ],
  },
  {
    element: <RequireAuth requireAdmin />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: "matches/pending", element: <MatchesPendingPage /> },
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
