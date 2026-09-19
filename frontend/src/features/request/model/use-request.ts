import { z } from "zod";

import { authParams, rqClient } from "@/shared/api/instance";
import { useRouteParams } from "@/shared/lib/router";

import { buildTimeline } from "../domain/timeline";
import { useRequestCategories } from "./use-request-categories";

const paramsSchema = z.object({ requestId: z.coerce.number().int() });

export const useRequest = () => {
  const params = useRouteParams(paramsSchema);

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

  // справочник нужен карточке ради зоны ответственности: в самой заявке её нет
  const categories = useRequestCategories();

  const request = card.data;

  return {
    request,
    zone:
      categories.data?.find(({ category }) => category === request?.category)
        ?.zone ?? null,
    timeline: request ? buildTimeline(request) : [],
    isPending: card.isPending,
    isError: params === null || card.isError,
    retry: () => void card.refetch(),
  };
};
