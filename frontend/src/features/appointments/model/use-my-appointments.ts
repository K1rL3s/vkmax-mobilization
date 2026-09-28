import { rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import { houseParams, useSession } from "@/shared/model/session";

import { appointmentState, type ReceptionSlot } from "../domain/schedule";

export const useMyAppointments = () => {
  const { currentResidency } = useSession();

  const list = rqClient.useQuery(
    "get",
    "/api/appointments",
    { params: houseParams() },
    {
      select: (data) =>
        data
          .filter(
            (item) =>
              appointmentState(item) === "upcoming" &&
              item.house_id === currentResidency?.house_id,
          )
          .sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at)),
    },
  );

  const items = list.data ?? [];
  const ownTimes = new Set(items.map((item) => Date.parse(item.starts_at)));

  return {
    items,
    isOwn: (slot: ReceptionSlot) => ownTimes.has(Date.parse(slot.starts_at)),
    isPending: list.isPending,
    isError: list.isError,
    loadError: list.error,
    retry: () => void list.refetch(),
  };
};

export const refetchAppointments = () =>
  invalidatePaths(
    "/api/appointments",
    "/api/houses/{house_id}/reception-slots",
  );
