import { generatePath, useNavigate } from "react-router-dom";

import { authParams, rqClient } from "@/shared/api/instance";
import { Routes } from "@/shared/model/routes";
import { useSession } from "@/shared/model/session";

import type { Flat, House } from "./types";

export const useHouseLink = () => {
  const navigate = useNavigate();
  const { residencies, reload } = useSession();

  const link = rqClient.useMutation("post", "/api/houses/{house_id}/link", {
    onSuccess: async (residency) => {
      await reload();

      // в подключенном доме сразу предлагаем подтвердить квартиру: про саму
      // фичу подтверждения онбординг не знает ничего, кроме маршрута
      const confirmation = generatePath(Routes.FLAT_CONFIRMATION, {
        residentId: String(residency.resident_id),
      });
      const next = residency.is_connected ? confirmation : Routes.HOME;

      await navigate(next, { state: { returnTo: Routes.HOME } });
    },
  });

  const linkedHouseIds = new Set(
    residencies.map((residency) => residency.house_id),
  );

  const submit = (house: House, flat: Flat | null, flatNumber: string) =>
    link.mutate({
      params: { ...authParams(), path: { house_id: house.id } },
      body: {
        role: "owner",
        source: "miniapp",
        ...(flat
          ? { flat_id: flat.id, entrance: flat.entrance }
          : { flat_number: flatNumber }),
      },
    });

  return {
    submit,
    isLinked: (houseId: number) => linkedHouseIds.has(houseId),
    isLinking: link.isPending || link.isSuccess,
    isFailed: link.isError,
  };
};
