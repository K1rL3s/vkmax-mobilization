import { redirect } from "react-router-dom";

import { loadHouseCard } from "@/shared/model/house";
import { isOnboarded, loadSession } from "@/shared/model/session";
import { Routes } from "@/shared/model/routes";

export const onboardedLoader = async () => {
  const session = await loadSession();

  if (!isOnboarded(session)) {
    throw redirect(Routes.WELCOME);
  }

  const current = session.residencies.at(-1);

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
