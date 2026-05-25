// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Arthur Michon
// See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { FormattedMessage, useIntl } from "react-intl";
import { cigarsApi, qk, type SearchHit } from "@/lib/queries";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Search } from "lucide-react";

const FORMATS = [
  "",
  "robusto",
  "toro",
  "corona",
  "churchill",
  "lonsdale",
  "panetela",
  "torpedo",
  "belicoso",
  "figurado",
  "other",
];

export function CigarsListPage() {
  const intl = useIntl();
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1");
  const page_size = 20;
  const brand = params.get("brand") ?? "";
  const format = params.get("format") ?? "";
  const isCuban = params.get("is_cuban");
  const q = params.get("q") ?? "";
  const [searchInput, setSearchInput] = useState(q);

  const listQuery = useQuery({
    queryKey: qk.cigars({
      page,
      page_size,
      brand,
      format,
      is_cuban: isCuban === "true",
    }),
    queryFn: () =>
      cigarsApi.list({
        page,
        page_size,
        brand: brand || undefined,
        format: format || undefined,
        is_cuban:
          isCuban === "true" ? true : isCuban === "false" ? false : undefined,
      }),
    placeholderData: keepPreviousData,
    enabled: !q,
  });

  const searchQuery = useQuery({
    queryKey: qk.search(q),
    queryFn: () => cigarsApi.search(q, 20),
    enabled: !!q,
  });

  const handleFilterChange = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete("page");
    setParams(next);
  };

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const next = new URLSearchParams(params);
    if (searchInput.trim()) next.set("q", searchInput.trim());
    else next.delete("q");
    next.delete("page");
    setParams(next);
  };

  const goPage = (n: number) => {
    const next = new URLSearchParams(params);
    next.set("page", String(n));
    setParams(next);
  };

  const items = q
    ? (searchQuery.data?.items ?? [])
    : (listQuery.data?.items ?? []);
  const total = q
    ? (searchQuery.data?.total ?? 0)
    : (listQuery.data?.total ?? 0);
  const totalPages = q ? 1 : (listQuery.data?.total_pages ?? 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          <FormattedMessage id="cigars.title" />
        </h1>
        <p className="text-muted-foreground">
          <FormattedMessage id="cigars.subtitle" />
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>
            <FormattedMessage id="cigars.filters" />
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={submitSearch} className="flex gap-2">
            <Input
              placeholder={intl.formatMessage({
                id: "cigars.searchPlaceholder",
              })}
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
            <Button type="submit" variant="default">
              <Search className="mr-2 h-4 w-4" />
              <FormattedMessage id="common.search" />
            </Button>
            {q && (
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setSearchInput("");
                  const next = new URLSearchParams(params);
                  next.delete("q");
                  setParams(next);
                }}
              >
                <FormattedMessage id="common.clear" />
              </Button>
            )}
          </form>
          <div className="grid gap-3 md:grid-cols-3">
            <div>
              <label className="text-xs uppercase text-muted-foreground">
                <FormattedMessage id="cigars.brand" />
              </label>
              <Input
                value={brand}
                placeholder="cohiba"
                onChange={(e) => handleFilterChange("brand", e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs uppercase text-muted-foreground">
                <FormattedMessage id="cigars.format" />
              </label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={format}
                onChange={(e) => handleFilterChange("format", e.target.value)}
              >
                {FORMATS.map((f) => (
                  <option key={f} value={f}>
                    {f || intl.formatMessage({ id: "common.any" })}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs uppercase text-muted-foreground">
                <FormattedMessage id="cigars.origin" />
              </label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={isCuban ?? ""}
                onChange={(e) => handleFilterChange("is_cuban", e.target.value)}
              >
                <option value="">
                  {intl.formatMessage({ id: "common.any" })}
                </option>
                <option value="true">
                  {intl.formatMessage({ id: "common.cuban" })}
                </option>
                <option value="false">
                  {intl.formatMessage({ id: "common.nonCuban" })}
                </option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            {q ? (
              <FormattedMessage id="cigars.searchTitle" values={{ q }} />
            ) : (
              <FormattedMessage id="cigars.catalogue" />
            )}
            <span className="ml-3 text-sm font-normal text-muted-foreground">
              <FormattedMessage
                id="cigars.resultsCount"
                values={{ count: total }}
              />
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>
                  <FormattedMessage id="cigars.fullName" />
                </TableHead>
                <TableHead>
                  <FormattedMessage id="cigars.vitola" />
                </TableHead>
                <TableHead>
                  <FormattedMessage id="cigars.format" />
                </TableHead>
                <TableHead>
                  <FormattedMessage id="cigars.origin" />
                </TableHead>
                {q && (
                  <TableHead>
                    <FormattedMessage id="common.score" />
                  </TableHead>
                )}
                {q && (
                  <TableHead>
                    <FormattedMessage id="cigars.matchedBy" />
                  </TableHead>
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((it) => {
                const cigar = q
                  ? (it as SearchHit).cigar
                  : (it as {
                      slug: string;
                      full_name: string;
                      vitola_name: string;
                      format_category: string;
                      is_cuban: boolean;
                    });
                const hit = q ? (it as SearchHit) : null;
                return (
                  <TableRow key={cigar.slug}>
                    <TableCell className="font-medium">
                      <Link
                        className="hover:underline"
                        to={`/cigars/${cigar.slug}`}
                      >
                        {cigar.full_name}
                      </Link>
                    </TableCell>
                    <TableCell>{cigar.vitola_name}</TableCell>
                    <TableCell>
                      <Badge variant="secondary">{cigar.format_category}</Badge>
                    </TableCell>
                    <TableCell>
                      {cigar.is_cuban ? (
                        <Badge variant="warning">
                          <FormattedMessage id="common.cuban" />
                        </Badge>
                      ) : (
                        <Badge variant="outline">
                          <FormattedMessage id="common.nonCuban" />
                        </Badge>
                      )}
                    </TableCell>
                    {hit && <TableCell>{hit.score.toFixed(4)}</TableCell>}
                    {hit && (
                      <TableCell>
                        {hit.matched_by.map((m) => (
                          <Badge key={m} variant="outline" className="mr-1">
                            {m}
                          </Badge>
                        ))}
                      </TableCell>
                    )}
                  </TableRow>
                );
              })}
              {!items.length && (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="text-center text-muted-foreground"
                  >
                    <FormattedMessage id="cigars.noResults" />
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>

          {!q && totalPages > 1 && (
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
                  onClick={() => goPage(page - 1)}
                >
                  <FormattedMessage id="common.previous" />
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={page >= totalPages}
                  onClick={() => goPage(page + 1)}
                >
                  <FormattedMessage id="common.next" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
