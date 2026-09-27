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

      const next = residency.is_connected
        ? generatePath(Routes.FLAT_CONFIRMATION, {
            residentId: String(residency.resident_id),
          })
        : Routes.HOME;

      await navigate(next, { replace: true, state: { returnTo: Routes.HOME } });
    },
  });

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
    isLinked: (houseId: number) =>
      residencies.some((residency) => residency.house_id === houseId),
    isLinking: link.isPending || link.isSuccess,
    error: link.error,
  };
};
