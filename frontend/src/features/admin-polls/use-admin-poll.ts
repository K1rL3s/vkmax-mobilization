import { z } from "zod";

import { useClosePoll } from "@/features/meetings";
import { authParams, rqClient } from "@/shared/api/instance";
import { useRouteParams } from "@/shared/lib/router";
import { orgParams } from "@/shared/model/session";

export const useAdminPoll = () => {
  const route = useRouteParams(
    z.object({ pollId: z.coerce.number().int().positive() }),
  );
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
    isPending: route !== null && (card.isPending || results.isPending),
    isError: route === null || card.isError || results.isError,
    loadError: card.error ?? results.error,
    retry: () => {
      void card.refetch();
      void results.refetch();
    },
  };
};
