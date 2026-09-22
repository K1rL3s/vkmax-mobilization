import { redirect } from "react-router-dom";

import { loadHouseCard } from "@/features/house";
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
