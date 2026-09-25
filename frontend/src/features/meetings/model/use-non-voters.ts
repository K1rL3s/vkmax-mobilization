import { z } from "zod";

import { isForbidden, retryUnlessForbidden } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { useRouteParams } from "@/shared/lib/router";

import { groupByEntrance } from "../domain/poll";

const paramsSchema = z.object({ pollId: z.coerce.number().int().positive() });

export const useNonVoters = () => {
  const route = useRouteParams(paramsSchema);

  const params = { ...authParams(), path: { poll_id: route?.pollId ?? 0 } };

  const flats = rqClient.useQuery(
    "get",
    "/api/polls/{poll_id}/non-voters",
    { params },
    {
      enabled: route !== null,
      retry: retryUnlessForbidden,
    },
  );

  const results = rqClient.useQuery(
    "get",
    "/api/polls/{poll_id}/results",
    { params },
    { enabled: route !== null },
  );

  const items = flats.data ?? [];

  return {
    items,
    totalFlats: results.data?.total_flats ?? null,
    isForbidden: isForbidden(flats.error),
    isPending: route !== null && flats.isPending,
    isError: route === null || flats.isError,
    retry: () => {
      void flats.refetch();
      void results.refetch();
    },
    groups: groupByEntrance(items),
  };
};
