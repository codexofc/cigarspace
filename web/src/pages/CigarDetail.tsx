// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Arthur Michon
// See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { FormattedMessage } from "react-intl";
import { cigarsApi, qk } from "@/lib/queries";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function DefinitionList({
  items,
}: {
  items: Array<[React.ReactNode, React.ReactNode]>;
}) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
      {items.map(([k, v], idx) => (
        <div key={idx} className="contents">
          <dt className="text-muted-foreground">{k}</dt>
          <dd className="font-medium">{v ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

export function CigarDetailPage() {
  const { slug = "" } = useParams();
  const detail = useQuery({
    queryKey: qk.cigar(slug),
    queryFn: () => cigarsApi.detail(slug),
    enabled: !!slug,
  });
  const matches = useQuery({
    queryKey: qk.cigarMatches(slug),
    queryFn: () => cigarsApi.customsMatches(slug),
    enabled: !!slug,
  });

  if (detail.isLoading)
    return (
      <p className="text-muted-foreground">
        <FormattedMessage id="common.loading" />
      </p>
    );
  if (detail.isError || !detail.data) {
    return (
      <p className="text-destructive">
        <FormattedMessage id="cigars.detail.notFound" />{" "}
        <Link className="underline" to="/cigars">
          <FormattedMessage id="cigars.detail.backToList" />
        </Link>
      </p>
    );
  }
  const c = detail.data;

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/cigars"
          className="text-sm text-muted-foreground hover:underline"
        >
          <FormattedMessage id="cigars.detail.back" />
        </Link>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">
          {c.full_name}
        </h1>
        <p className="mt-1 text-muted-foreground">
          {c.vitola_name} ·{" "}
          <Badge variant="secondary" className="ml-1">
            {c.format_category}
          </Badge>
          {c.is_cuban && (
            <Badge variant="warning" className="ml-2">
              <FormattedMessage id="common.cuban" />
            </Badge>
          )}
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>
              <FormattedMessage id="cigars.detail.specs" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <DefinitionList
              items={[
                [
                  <FormattedMessage id="cigars.detail.lengthMm" />,
                  c.length_mm ?? "—",
                ],
                [
                  <FormattedMessage id="cigars.detail.ringGauge" />,
                  c.ring_gauge ?? "—",
                ],
                [
                  <FormattedMessage id="cigars.detail.diameterMm" />,
                  c.ring_gauge_mm ?? "—",
                ],
                [
                  <FormattedMessage id="cigars.detail.weightG" />,
                  c.weight_g ?? "—",
                ],
                [
                  <FormattedMessage id="cigars.detail.strength" />,
                  c.strength ?? "—",
                ],
                [<FormattedMessage id="cigars.detail.body" />, c.body ?? "—"],
                [
                  <FormattedMessage id="cigars.detail.releaseYear" />,
                  c.release_year ?? "—",
                ],
              ]}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>
              <FormattedMessage id="cigars.detail.origins" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <DefinitionList
              items={[
                [
                  <FormattedMessage id="cigars.detail.wrapper" />,
                  c.wrapper_country ?? "—",
                ],
                [
                  <FormattedMessage id="cigars.detail.binder" />,
                  c.binder_country ?? "—",
                ],
                [
                  <FormattedMessage id="cigars.detail.fillers" />,
                  c.filler_countries.join(", ") || "—",
                ],
              ]}
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>
            <FormattedMessage
              id="cigars.detail.blendCount"
              values={{ count: c.blend_components.length }}
            />
          </CardTitle>
        </CardHeader>
        <CardContent>
          {c.blend_components.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>
                    <FormattedMessage id="cigars.detail.type" />
                  </TableHead>
                  <TableHead>
                    <FormattedMessage id="cigars.detail.origins" />
                  </TableHead>
                  <TableHead>
                    <FormattedMessage id="cigars.detail.region" />
                  </TableHead>
                  <TableHead>
                    <FormattedMessage id="cigars.detail.variety" />
                  </TableHead>
                  <TableHead>
                    <FormattedMessage id="cigars.detail.aging" />
                  </TableHead>
                  <TableHead>
                    <FormattedMessage id="cigars.detail.confidence" />
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {c.blend_components.map((b, idx) => (
                  <TableRow key={idx}>
                    <TableCell>{b.component_type}</TableCell>
                    <TableCell>{b.tobacco_origin ?? "—"}</TableCell>
                    <TableCell>{b.tobacco_region ?? "—"}</TableCell>
                    <TableCell>{b.tobacco_variety ?? "—"}</TableCell>
                    <TableCell>{b.aging_years ?? "—"}</TableCell>
                    <TableCell>{b.source_confidence}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">
              <FormattedMessage id="cigars.detail.noBlend" />
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            <FormattedMessage
              id="cigars.detail.matchesCount"
              values={{ count: matches.data?.length ?? 0 }}
            />
          </CardTitle>
        </CardHeader>
        <CardContent>
          {matches.data && matches.data.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>
                    <FormattedMessage id="common.status" />
                  </TableHead>
                  <TableHead>
                    <FormattedMessage id="common.score" />
                  </TableHead>
                  <TableHead>
                    <FormattedMessage id="cigars.detail.pack" />
                  </TableHead>
                  <TableHead>
                    <FormattedMessage id="cigars.detail.method" />
                  </TableHead>
                  <TableHead>
                    <FormattedMessage id="cigars.detail.reviewedBy" />
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {matches.data.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell>
                      <Badge
                        variant={
                          m.status === "human_accepted"
                            ? "success"
                            : "secondary"
                        }
                      >
                        {m.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{m.score}</TableCell>
                    <TableCell>{m.pack_size_bucket ?? "—"}</TableCell>
                    <TableCell>{m.match_method}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {m.reviewed_by ?? m.matched_by}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">
              <FormattedMessage id="cigars.detail.noMatches" />
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
