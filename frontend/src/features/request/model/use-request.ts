import { z } from "zod";

import { authParams, rqClient } from "@/shared/api/instance";
import { useRouteParams } from "@/shared/lib/router";

import { useRequestCategories } from "./use-request-categories";

export const useRequest = () => {
  const params = useRouteParams(
    z.object({ requestId: z.coerce.number().int().positive() }),
  );

  const card = rqClient.useQuery(
    "get",
    "/api/requests/{request_id}",
    {
      params: {
        ...authParams(),
        path: { request_id: params?.requestId ?? 0 },
      },
    },
    { enabled: params !== null },
  );

  const categories = useRequestCategories();

  const request = card.data;

  return {
    request,
    zone:
      categories.data?.find(({ category }) => category === request?.category)
        ?.zone ?? null,
    isPending: params !== null && card.isPending,
    isError: params === null || card.isError,
    loadError: card.error,
    retry: () => void card.refetch(),
  };
};
