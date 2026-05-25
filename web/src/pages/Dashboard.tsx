// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Arthur Michon
// See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { FormattedMessage, useIntl } from "react-intl";
import { adminApi, cigarsApi, customsApi, matchesApi, qk } from "@/lib/queries";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Cigarette,
  ClipboardCheck,
  CheckCircle2,
  RefreshCw,
} from "lucide-react";
import { useAuthStore } from "@/stores/auth";
import { useState, type ReactNode } from "react";
import { formatDate } from "@/lib/utils";

function StatCard({
  title,
  value,
  icon: Icon,
  description,
}: {
  title: ReactNode;
  value: ReactNode;
  icon: typeof Cigarette;
  description?: ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </CardContent>
    </Card>
  );
}

export function DashboardPage() {
  const intl = useIntl();
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const qc = useQueryClient();

  const cigars = useQuery({
    queryKey: qk.cigars({ page: 1, page_size: 1 }),
    queryFn: () => cigarsApi.list({ page: 1, page_size: 1 }),
  });
  const accepted = useQuery({
    queryKey: qk.matches({ page: 1, page_size: 1, status: ["auto_accepted"] }),
    queryFn: () =>
      matchesApi.list({ page: 1, page_size: 1, status: ["auto_accepted"] }),
    enabled: !!useAuthStore.getState().accessToken,
  });
  const pending = useQuery({
    queryKey: qk.matches({ page: 1, page_size: 1, status: ["pending_review"] }),
    queryFn: () =>
      matchesApi.list({ page: 1, page_size: 1, status: ["pending_review"] }),
    enabled: isAdmin,
  });
  const sources = useQuery({
    queryKey: qk.customsSources,
    queryFn: () => customsApi.sources(),
  });

  const [jobMessage, setJobMessage] = useState<string | null>(null);
  const refreshMut = useMutation({
    mutationFn: (code: string) => adminApi.refreshCustomsSource(code),
    onSuccess: (data, code) => {
      setJobMessage(
        intl.formatMessage(
          { id: "dashboard.refreshQueued" },
          { code, jobId: data.job_id },
        ),
      );
      qc.invalidateQueries({ queryKey: qk.customsSources });
    },
  });
  const matchAllMut = useMutation({
    mutationFn: () => adminApi.rerunMatchingAll(),
    onSuccess: (data) => {
      setJobMessage(
        intl.formatMessage(
          { id: "dashboard.matchingQueued" },
          { jobId: data.job_id },
        ),
      );
      qc.invalidateQueries({ queryKey: qk.matches() });
    },
  });

  const activeSources = sources.data?.items.filter((s) => s.is_active) ?? [];
  const lastChecked = activeSources
    .map((s) => s.last_checked_at)
    .filter(Boolean)
    .sort()
    .at(-1);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          <FormattedMessage id="dashboard.title" />
        </h1>
        <p className="text-muted-foreground">
          <FormattedMessage id="dashboard.subtitle" />
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title={<FormattedMessage id="dashboard.cigarsCount" />}
          value={cigars.data?.total ?? "—"}
          icon={Cigarette}
        />
        <StatCard
          title={<FormattedMessage id="dashboard.matchesAccepted" />}
          value={accepted.data?.total ?? "—"}
          icon={CheckCircle2}
          description={<FormattedMessage id="dashboard.matchesAcceptedHint" />}
        />
        <StatCard
          title={<FormattedMessage id="dashboard.pendingReview" />}
          value={
            isAdmin ? (
              (pending.data?.total ?? "—")
            ) : (
              <FormattedMessage id="dashboard.pendingReviewAdminOnly" />
            )
          }
          icon={ClipboardCheck}
        />
        <StatCard
          title={<FormattedMessage id="dashboard.activeSources" />}
          value={activeSources.length}
          icon={RefreshCw}
          description={
            lastChecked ? (
              <FormattedMessage
                id="dashboard.lastCheck"
                values={{ date: formatDate(lastChecked) }}
              />
            ) : (
              "—"
            )
          }
        />
      </div>

      {isAdmin && (
        <Card>
          <CardHeader>
            <CardTitle>
              <FormattedMessage id="dashboard.adminActions" />
            </CardTitle>
            <CardDescription>
              <FormattedMessage id="dashboard.adminActionsDesc" />
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <p className="text-sm font-medium">
                <FormattedMessage id="dashboard.refreshSource" />
              </p>
              <div className="flex flex-wrap gap-2">
                {activeSources.map((s) => (
                  <Button
                    key={s.code}
                    size="sm"
                    variant="outline"
                    disabled={refreshMut.isPending}
                    onClick={() => refreshMut.mutate(s.code)}
                  >
                    <RefreshCw className="mr-2 h-4 w-4" />
                    {s.code}
                  </Button>
                ))}
                {!activeSources.length && (
                  <p className="text-sm text-muted-foreground">
                    <FormattedMessage id="dashboard.noActiveSource" />
                  </p>
                )}
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium">
                <FormattedMessage id="dashboard.rerunMatching" />
              </p>
              <Button
                size="sm"
                disabled={matchAllMut.isPending}
                onClick={() => matchAllMut.mutate()}
              >
                <RefreshCw className="mr-2 h-4 w-4" />
                <FormattedMessage id="dashboard.rerunMatchingBtn" />
              </Button>
            </div>
            {jobMessage && (
              <Badge variant="success" className="mt-2">
                {jobMessage}
              </Badge>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
