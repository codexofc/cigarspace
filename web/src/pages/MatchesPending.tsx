// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Arthur Michon
// See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormattedMessage, useIntl } from "react-intl";
import { matchesApi, qk, type CustomsMatchResponse } from "@/lib/queries";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CheckCircle2, XCircle } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { ApiError } from "@/lib/api-client";

export function MatchesPendingPage() {
  const intl = useIntl();
  const [page, setPage] = useState(1);
  const page_size = 20;
  const [selected, setSelected] = useState<CustomsMatchResponse | null>(null);
  const [decision, setDecision] = useState<"human_accepted" | "human_rejected">(
    "human_accepted",
  );
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const qc = useQueryClient();

  const list = useQuery({
    queryKey: qk.matches({ page, page_size, status: ["pending_review"] }),
    queryFn: () =>
      matchesApi.list({ page, page_size, status: ["pending_review"] }),
  });

  const decideMutation = useMutation({
    mutationFn: ({
      id,
      status,
      notes,
    }: {
      id: string;
      status: "human_accepted" | "human_rejected";
      notes: string;
    }) => matchesApi.decide(id, status, notes || undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.matches() });
      setSelected(null);
      setNotes("");
      setError(null);
    },
    onError: (err) => {
      if (err instanceof ApiError) setError(err.body?.detail ?? err.message);
      else setError(String(err));
    },
  });

  const openDialog = (
    m: CustomsMatchResponse,
    status: "human_accepted" | "human_rejected",
  ) => {
    setSelected(m);
    setDecision(status);
    setNotes("");
    setError(null);
  };

  const total = list.data?.total ?? 0;
  const totalPages = list.data?.total_pages ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          <FormattedMessage id="matches.title" />
        </h1>
        <p className="text-muted-foreground">
          <FormattedMessage id="matches.subtitle" />
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>
            <FormattedMessage
              id="matches.pendingCount"
              values={{ count: total }}
            />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>
                  <FormattedMessage id="matches.cigar" />
                </TableHead>
                <TableHead>
                  <FormattedMessage id="matches.customs" />
                </TableHead>
                <TableHead>
                  <FormattedMessage id="matches.pack" />
                </TableHead>
                <TableHead>
                  <FormattedMessage id="common.score" />
                </TableHead>
                <TableHead>
                  <FormattedMessage id="matches.signals" />
                </TableHead>
                <TableHead>
                  <FormattedMessage id="matches.matchedAt" />
                </TableHead>
                <TableHead>
                  <FormattedMessage id="common.actions" />
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(list.data?.items ?? []).map((m) => (
                <TableRow key={m.id}>
                  <TableCell className="max-w-[260px] truncate text-xs text-muted-foreground">
                    {m.cigar_id}
                  </TableCell>
                  <TableCell className="max-w-[260px] truncate text-xs text-muted-foreground">
                    {m.customs_entry_id}
                  </TableCell>
                  <TableCell>{m.pack_size_bucket ?? "—"}</TableCell>
                  <TableCell>
                    <Badge
                      variant={Number(m.score) >= 0.8 ? "success" : "warning"}
                    >
                      {m.score}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs">
                    {Object.entries(m.signals).map(([k, v]) => (
                      <span key={k} className="mr-2 inline-block">
                        <span className="text-muted-foreground">{k}:</span>{" "}
                        {v.toFixed(2)}
                      </span>
                    ))}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {formatDate(m.matched_at)}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => openDialog(m, "human_accepted")}
                      >
                        <CheckCircle2 className="mr-1 h-4 w-4" />
                        <FormattedMessage id="matches.accept" />
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => openDialog(m, "human_rejected")}
                      >
                        <XCircle className="mr-1 h-4 w-4" />
                        <FormattedMessage id="matches.reject" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!list.data?.items.length && (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="text-center text-muted-foreground"
                  >
                    <FormattedMessage id="matches.nothingPending" />
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                <FormattedMessage
                  id="cigars.pagination"
                  values={{ page, totalPages }}
                />
              </p>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  <FormattedMessage id="common.previous" />
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  <FormattedMessage id="common.next" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog
        open={!!selected}
        onOpenChange={(open) => !open && setSelected(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              <FormattedMessage
                id={
                  decision === "human_accepted"
                    ? "matches.dialog.acceptTitle"
                    : "matches.dialog.rejectTitle"
                }
              />
            </DialogTitle>
            <DialogDescription>
              <FormattedMessage
                id={
                  decision === "human_accepted"
                    ? "matches.dialog.acceptDesc"
                    : "matches.dialog.rejectDesc"
                }
              />
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="notes">
              <FormattedMessage id="matches.dialog.notesLabel" />
            </Label>
            <Input
              id="notes"
              placeholder={intl.formatMessage({
                id: "matches.dialog.notesPlaceholder",
              })}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setSelected(null)}>
              <FormattedMessage id="common.cancel" />
            </Button>
            <Button
              variant={
                decision === "human_accepted" ? "default" : "destructive"
              }
              disabled={decideMutation.isPending}
              onClick={() =>
                selected &&
                decideMutation.mutate({
                  id: selected.id,
                  status: decision,
                  notes,
                })
              }
            >
              <FormattedMessage id="common.confirm" />
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
