import { generatePath, redirect } from "react-router-dom";

import {
  defaultRouteForSession,
  executeDeeplink,
  ignoreDeeplink,
  openPathDeeplink,
  parseStartParam,
  runDeeplinkOnce,
  shouldHandleDeeplink,
  type DeeplinkPageState,
} from "@/features/deeplink";
import { getMaxLaunch } from "@/shared/lib/max";
import { Routes } from "@/shared/model/routes";
import { loadSession } from "@/shared/model/session";

const newRequestRoute = (category: string) =>
  `${Routes.REQUEST_NEW}?${new URLSearchParams({ category }).toString()}`;

export const deeplinkLoader = async (): Promise<DeeplinkPageState> => {
  const raw = getMaxLaunch().startParam;
  const command = parseStartParam(raw);
  const session = await loadSession();

  if (!raw || !command) {
    throw redirect(defaultRouteForSession(session));
  }

  if (command.kind === "path" && command.path === Routes.PRIVACY) {
    ignoreDeeplink(raw);
    throw redirect(Routes.PRIVACY);
  }

  if (session.consent_at === null) {
    return { status: "consent" };
  }

  if (!shouldHandleDeeplink(raw)) {
    throw redirect(defaultRouteForSession(session));
  }

  if (command.kind === "invite") {
    return {
      status: "bot-only",
      hasResidency: session.residencies.length > 0,
    };
  }

  if (command.kind === "register" || command.kind === "path") {
    const route =
      command.kind === "register"
        ? generatePath(Routes.REGISTER, { code: command.code })
        : await openPathDeeplink(command.path, session);

    ignoreDeeplink(raw);

    if (route === null) {
      return { status: "no-access", route: defaultRouteForSession(session) };
    }

    throw redirect(route);
  }

  const attempt = await runDeeplinkOnce(raw, () => executeDeeplink(command));

  if (attempt.status === "ignored") {
    throw redirect(defaultRouteForSession(session));
  }

  if (attempt.status === "failed") {
    return {
      status: "failure",
      kind: command.kind,
      hasResidency: session.residencies.length > 0,
      error: attempt.error,
    };
  }

  if (command.kind === "house" && command.category !== null) {
    throw redirect(newRequestRoute(command.category));
  }

  throw redirect(
    attempt.value.target === "resident" ? Routes.HOME : Routes.ADMIN_REQUESTS,
  );
};
