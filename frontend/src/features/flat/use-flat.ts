import { useQuery } from "@tanstack/react-query";

import {
  confirmationCaption,
  confirmationView,
} from "@/features/flat-confirmation";
import type { components } from "@/shared/api/schema/generated";
import { authParams, rqClient } from "@/shared/api/instance";
import { useSession } from "@/shared/model/session";

export type FlatCard = components["schemas"]["FlatCard"];

export const useFlat = () => {
  const { currentResidency: residency } = useSession();
  const flatId = residency?.flat_id ?? null;

  const card = useQuery({
    ...rqClient.queryOptions("get", "/api/flats/{flat_id}", {
      params: { ...authParams(), path: { flat_id: flatId ?? 0 } },
    }),
    enabled: flatId !== null,
  });

  if (!residency) {
    return { residency: null };
  }

  const view = confirmationView(residency);

  return {
    residency,
    card,
    view,
    // подтверждать нечего, пока УК не подключена или не завела квартиру
    canConfirm:
      residency.is_connected && view !== "verified" && view !== "no-flat",
    caption: residency.is_connected
      ? confirmationCaption(residency)
      : "дом ещё не подключён к сервису",
    title: residency.flat_number
      ? `Квартира ${residency.flat_number}`
      : "Квартира",
  };
};
