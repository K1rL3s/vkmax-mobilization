import { z } from "zod";

import { useClosePoll } from "@/features/meetings";
import { authParams, rqClient } from "@/shared/api/instance";
import { useRouteParams } from "@/shared/lib/router";
import { orgParams } from "@/shared/model/session";

const paramsSchema = z.object({ pollId: z.coerce.number().int().positive() });

// карточку и результаты бэк отдаёт сотруднику УК дома по тем же ручкам, что и
// жителю: кворум считает он, фронт его не пересчитывает
export const useAdminPoll = () => {
  const route = useRouteParams(paramsSchema);
  const params = { ...authParams(), path: { poll_id: route?.pollId ?? 0 } };

  const card = rqClient.useQuery(
    "get",
    "/api/polls/{poll_id}",
    { params },
    { enabled: route !== null },
  );

  const results = rqClient.useQuery(
    "get",
    "/api/polls/{poll_id}/results",
    { params },
    { enabled: route !== null },
  );

  // адрес в карточке опроса не приходит; не загрузился - шапка обходится без него
  const houses = rqClient.useQuery("get", "/api/admin/houses", {
    params: { ...orgParams(), query: { limit: 100 } },
  });

  const poll = card.data;

  return {
    poll,
    results: results.data,
    address: houses.data?.items.find((house) => house.id === poll?.house_id)
      ?.address,
    closing: useClosePoll(route?.pollId ?? 0),
    // выключенный запрос висит в pending: без проверки кривой адрес крутил
    // бы загрузку вечно
    isPending: route !== null && (card.isPending || results.isPending),
    isError: route === null || card.isError || results.isError,
    retry: () => {
      void card.refetch();
      void results.refetch();
    },
  };
};
