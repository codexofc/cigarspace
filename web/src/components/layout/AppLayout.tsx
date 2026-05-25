// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Arthur Michon
// See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LogOut,
  LayoutDashboard,
  Cigarette,
  ClipboardCheck,
  User2,
  Globe,
} from "lucide-react";
import { FormattedMessage, useIntl } from "react-intl";
import { useAuthStore } from "@/stores/auth";
import { authApi } from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useLocale, SUPPORTED_LOCALES } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";

interface NavItem {
  to: string;
  labelId: string;
  icon: typeof LayoutDashboard;
  end?: boolean;
  admin?: boolean;
}

const navItems: NavItem[] = [
  { to: "/", labelId: "nav.dashboard", icon: LayoutDashboard, end: true },
  { to: "/cigars", labelId: "nav.cigars", icon: Cigarette },
  {
    to: "/matches/pending",
    labelId: "nav.reviewQueue",
    icon: ClipboardCheck,
    admin: true,
  },
  { to: "/me", labelId: "nav.profile", icon: User2 },
];

function LanguageSwitcher() {
  const { locale, setLocale } = useLocale();
  const intl = useIntl();
  return (
    <label className="mb-2 flex items-center gap-2 px-3 text-xs text-muted-foreground">
      <Globe className="h-3 w-3" />
      <span className="sr-only">
        {intl.formatMessage({ id: "language.switch" })}
      </span>
      <select
        value={locale}
        onChange={(e) => setLocale(e.target.value as Locale)}
        className="bg-transparent text-xs focus:outline-none"
      >
        {SUPPORTED_LOCALES.map((code) => (
          <option key={code} value={code}>
            {intl.formatMessage({ id: `language.${code}` })}
          </option>
        ))}
      </select>
    </label>
  );
}

export function AppLayout() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const clear = useAuthStore((s) => s.clear);
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      /* still clear locally even if the server call fails */
    }
    clear();
    navigate("/login", { replace: true });
  };

  return (
    <div className="flex min-h-screen bg-muted/20">
      <aside className="hidden w-64 shrink-0 border-r bg-background md:flex md:flex-col">
        <div className="border-b px-6 py-5">
          <h1 className="text-lg font-semibold">
            <FormattedMessage id="common.appName" />
          </h1>
          <p className="text-xs text-muted-foreground">
            <FormattedMessage id="common.tagline" />
          </p>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {navItems.map((item) => {
            if (item.admin && !isAdmin) return null;
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition",
                    isActive
                      ? "bg-secondary text-secondary-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                  )
                }
              >
                <Icon className="h-4 w-4" />
                <FormattedMessage id={item.labelId} />
              </NavLink>
            );
          })}
        </nav>
        <div className="border-t p-3">
          <LanguageSwitcher />
          <div className="mb-2 px-3 text-xs text-muted-foreground">
            <div className="truncate">{user?.email ?? "—"}</div>
            <div className="truncate">
              <FormattedMessage
                id={isAdmin ? "common.admin" : "common.reader"}
              />
            </div>
          </div>
          <Button
            variant="ghost"
            className="w-full justify-start gap-2"
            onClick={handleLogout}
          >
            <LogOut className="h-4 w-4" />{" "}
            <FormattedMessage id="common.logout" />
          </Button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="container py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
