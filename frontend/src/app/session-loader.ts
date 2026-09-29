import { redirect, replace } from "react-router-dom";

import { loadHouseCard } from "@/features/house";
import {
  defaultRouteForSession,
  parseStartParam,
  shouldHandleDeeplink,
} from "@/features/deeplink";
import { getMaxLaunch } from "@/shared/lib/max";
import {
  currentResidency,
  hasWorkingOrg,
  isOnboarded,
  loadSession,
  startTarget,
} from "@/shared/model/session";
import { Routes } from "@/shared/model/routes";

export const onboardedLoader = async () => {
  const session = await loadSession();

  if (!isOnboarded(session)) {
    throw redirect(defaultRouteForSession(session));
  }

  const current = currentResidency(session);

  if (current) {
    await loadHouseCard(current.house_id);
  }

  return null;
};

export const welcomeLoader = async () => {
  const raw = getMaxLaunch().startParam;

  if (raw && parseStartParam(raw) && shouldHandleDeeplink(raw)) {
    throw replace(Routes.DEEPLINK);
  }

  const session = await loadSession();

  if (startTarget(session) !== "onboarding") {
    throw replace(defaultRouteForSession(session));
  }

  return null;
};

export const adminLoader = async () => {
  if (!hasWorkingOrg(await loadSession())) {
    throw redirect(Routes.HOME);
  }

  return null;
};

export const sessionLoader = async () => {
  await loadSession();

  return null;
};
