import { z } from "zod";

import { isForbidden } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { useRouteParams } from "@/shared/lib/router";

import { groupByEntrance } from "../domain/poll";

const paramsSchema = z.object({ pollId: z.coerce.number().int() });

export const useNonVoters = () => {
  const route = useRouteParams(paramsSchema);

  const params = { ...authParams(), path: { poll_id: route?.pollId ?? 0 } };

  const flats = rqClient.useQuery(
    "get",
    "/api/polls/{poll_id}/non-voters",
    { params },
    {
      enabled: route !== null,
      // отказ в правах повторять нечего: без этого житель три попытки
      // смотрит на «Загружаем квартиры» вместо объяснения
      retry: (count, error) => !isForbidden(error) && count < 3,
    },
  );

  // общее число квартир живёт только в результатах, отдельной ручки нет
  const results = rqClient.useQuery(
    "get",
    "/api/polls/{poll_id}/results",
    { params },
    { enabled: route !== null },
  );

  const items = flats.data ?? [];
  const groups = groupByEntrance(items);

  return {
    pollId: route?.pollId ?? null,
    items,
    totalFlats: results.data?.total_flats ?? null,
    // права могли измениться, пока экран открыт: 403 объясняем словами, а не
    // общей ошибкой загрузки
    isForbidden: isForbidden(flats.error),
    isPending: flats.isPending,
    isError: route === null || flats.isError,
    retry: () => {
      void flats.refetch();
      void results.refetch();
    },
    groups,
  };
};
