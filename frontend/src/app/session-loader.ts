import { redirect } from "react-router-dom";

import { loadHouseCard } from "@/features/house";
import { parseStartParam, shouldHandleDeeplink } from "@/features/deeplink";
import { getMaxLaunch } from "@/shared/lib/max";
import {
  currentResidency,
  hasWorkingOrg,
  isOnboarded,
  loadSession,
  startTarget,
  type StartTarget,
} from "@/shared/model/session";
import { Routes } from "@/shared/model/routes";

const startRoute = (target: StartTarget) => {
  switch (target) {
    case "admin":
      return Routes.ADMIN;
    case "home":
      return Routes.HOME;
    case "onboarding":
      return Routes.WELCOME;
  }
};

export const onboardedLoader = async () => {
  const session = await loadSession();

  if (!isOnboarded(session)) {
    throw redirect(startRoute(startTarget(session)));
  }

  const current = currentResidency(session);

  if (current) {
    await loadHouseCard(current.house_id);
  }

  return null;
};

export const welcomeLoader = async () => {
  const raw = getMaxLaunch().startParam;

  // После отказа от bot-only команды тот же startParam остаётся в MAX launch
  // data до перезагрузки. Без runtime-флага переход на / зациклится через
  // /launch вместо обычного старта приложения.
  if (raw && parseStartParam(raw) && shouldHandleDeeplink(raw)) {
    throw redirect(Routes.DEEPLINK);
  }

  const target = startTarget(await loadSession());

  if (target !== "onboarding") {
    throw redirect(startRoute(target));
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
