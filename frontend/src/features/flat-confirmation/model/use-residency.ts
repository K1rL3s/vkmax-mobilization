import { useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { useRouteParams } from "@/shared/lib/router";
import { Routes } from "@/shared/model/routes";
import { useSession } from "@/shared/model/session";

const paramsSchema = z.object({ residentId: z.coerce.number().int() });

// что передал предыдущий экран: куда возвращаться и уже набранный лицевой
// счет. Кладет это вызывающая сторона, но доезжает оно через историю браузера
const historyState = z
  .object({ returnTo: z.string().startsWith("/"), accountNo: z.string() })
  .partial();

export const useResidency = () => {
  const params = useRouteParams(paramsSchema);
  const { state } = useLocation();
  const navigate = useNavigate();
  const { residencies, reload } = useSession();

  const residency = residencies.find(
    (item) => item.resident_id === params?.residentId,
  );
  const handover = historyState.safeParse(state).data;
  const returnTo = handover?.returnTo ?? Routes.HOME;

  return {
    residency,
    returnTo,
    prefilledAccountNo: handover?.accountNo ?? "",
    reload,
    exit: () => void navigate(returnTo, { replace: true }),
  };
};
