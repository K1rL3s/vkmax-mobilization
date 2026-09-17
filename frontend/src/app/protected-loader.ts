import { redirect } from "react-router-dom";

import { getMaxLaunch } from "@/shared/lib/max";
import { Routes } from "@/shared/model/routes";

export const protectedLoader = () => {
  if (getMaxLaunch().isInsideMax) {
    return null;
  }

  throw redirect(Routes.OUTSIDE_MAX);
};
