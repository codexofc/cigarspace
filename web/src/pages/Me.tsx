// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Arthur Michon
// See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
import { FormattedMessage } from "react-intl";
import { useAuthStore } from "@/stores/auth";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function MePage() {
  const user = useAuthStore((s) => s.user);
  const scopes = useAuthStore((s) => s.scopes);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          <FormattedMessage id="me.title" />
        </h1>
        <p className="text-muted-foreground">
          <FormattedMessage id="me.subtitle" />
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>{user?.email ?? "—"}</CardTitle>
          <CardDescription>
            {user?.full_name ?? <FormattedMessage id="me.noFullName" />}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">
              <FormattedMessage id="common.status" />:
            </span>
            {user?.is_active ? (
              <Badge variant="success">
                <FormattedMessage id="common.active" />
              </Badge>
            ) : (
              <Badge variant="destructive">
                <FormattedMessage id="common.disabled" />
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">
              <FormattedMessage id="common.role" />:
            </span>
            <Badge variant={user?.is_admin ? "default" : "secondary"}>
              <FormattedMessage
                id={user?.is_admin ? "common.admin" : "common.reader"}
              />
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">
              <FormattedMessage id="me.scopes" />:
            </span>
            {scopes.map((s) => (
              <Badge key={s} variant="outline">
                {s}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
