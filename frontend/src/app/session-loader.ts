import { redirect } from "react-router-dom";

import { loadHouseCard } from "@/features/house";
import { parseStartParam, shouldHandleDeeplink } from "@/features/deeplink";
import { getMaxLaunch } from "@/shared/lib/max";
import {
  currentResidency,
  isOnboarded,
  loadSession,
} from "@/shared/model/session";
import { Routes } from "@/shared/model/routes";

export const onboardedLoader = async () => {
  const session = await loadSession();

  if (!isOnboarded(session)) {
    throw redirect(Routes.WELCOME);
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

  if (isOnboarded(await loadSession())) {
    throw redirect(Routes.HOME);
  }

  return null;
};

export const adminLoader = async () => {
  const session = await loadSession();

  if (session.orgs.length === 0) {
    throw redirect(Routes.HOME);
  }

  return null;
};

export const sessionLoader = async () => {
  await loadSession();

  return null;
};
