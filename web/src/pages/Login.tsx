// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Arthur Michon
// See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate, useLocation } from "react-router-dom";
import { FormattedMessage, useIntl } from "react-intl";
import { authApi } from "@/lib/queries";
import { useAuthStore } from "@/stores/auth";
import { ApiError } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface LoginForm {
  email: string;
  password: string;
}

export function LoginPage() {
  const intl = useIntl();
  const { register, handleSubmit, formState } = useForm<LoginForm>({
    defaultValues: { email: "", password: "" },
  });
  const [serverError, setServerError] = useState<string | null>(null);
  const setAccess = useAuthStore((s) => s.setAccess);
  const setUser = useAuthStore((s) => s.setUser);
  const navigate = useNavigate();
  const location = useLocation();
  const next =
    (location.state as { from?: { pathname: string } } | null)?.from
      ?.pathname ?? "/";

  const onSubmit = async (values: LoginForm) => {
    setServerError(null);
    try {
      const tokens = await authApi.login(values.email, values.password);
      setAccess({
        token: tokens.access_token,
        expiresIn: tokens.expires_in,
        scopes: tokens.scope.split(" ").filter(Boolean),
      });
      const me = await authApi.me();
      setUser(me);
      navigate(next, { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setServerError(err.body?.detail ?? err.message);
      } else {
        setServerError(intl.formatMessage({ id: "login.networkError" }));
      }
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>
            <FormattedMessage id="login.title" />
          </CardTitle>
          <CardDescription>
            <FormattedMessage id="login.description" />
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">
                <FormattedMessage id="common.email" />
              </Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                {...register("email", { required: true })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">
                <FormattedMessage id="common.password" />
              </Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                {...register("password", { required: true })}
              />
            </div>
            {serverError && (
              <p role="alert" className="text-sm font-medium text-destructive">
                {serverError}
              </p>
            )}
            <Button
              type="submit"
              className="w-full"
              disabled={formState.isSubmitting}
            >
              <FormattedMessage
                id={
                  formState.isSubmitting ? "common.signingIn" : "common.signIn"
                }
              />
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
