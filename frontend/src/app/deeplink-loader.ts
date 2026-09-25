import { redirect } from "react-router-dom";

import {
  defaultRouteForSession,
  executeDeeplink,
  parseStartParam,
  runDeeplinkOnce,
  shouldHandleDeeplink,
  type DeeplinkPageState,
} from "@/features/deeplink";
import { getMaxLaunch } from "@/shared/lib/max";
import { Routes } from "@/shared/model/routes";
import { loadSession } from "@/shared/model/session";

export const deeplinkLoader = async (): Promise<DeeplinkPageState> => {
  const raw = getMaxLaunch().startParam;
  const command = parseStartParam(raw);
  const session = await loadSession();

  if (!raw || !command) {
    throw redirect(defaultRouteForSession(session));
  }

  if (session.consent_at === null) {
    return { status: "consent" };
  }

  if (!shouldHandleDeeplink(raw)) {
    throw redirect(defaultRouteForSession(session));
  }

  if (command.kind === "invite" || command.kind === "register") {
    return {
      status: "bot-only",
      hasResidency: session.residencies.length > 0,
    };
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
    };
  }

  throw redirect(
    attempt.value.target === "resident" ? Routes.HOME : Routes.ADMIN_REQUESTS,
  );
};
