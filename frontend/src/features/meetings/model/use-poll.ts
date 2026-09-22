import { useState } from "react";
import { z } from "zod";

import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import { useRouteParams } from "@/shared/lib/router";
import { useSession } from "@/shared/model/session";

const paramsSchema = z.object({ pollId: z.coerce.number().int() });

export const usePoll = () => {
  const route = useRouteParams(paramsSchema);
  const { currentResidency: residency } = useSession();
  const [chosen, setChosen] = useState<number[]>([]);

  const params = {
    ...authParams(),
    path: { poll_id: route?.pollId ?? 0 },
  };

  const card = rqClient.useQuery(
    "get",
    "/api/polls/{poll_id}",
    { params },
    {
      enabled: route !== null,
    },
  );

  const results = rqClient.useQuery(
    "get",
    "/api/polls/{poll_id}/results",
    { params },
    { enabled: route !== null },
  );

  const vote = rqClient.useMutation("post", "/api/polls/{poll_id}/vote", {
    // готовые результаты из ответа выбрасываем: состояние экрана приезжает
    // инвалидацией, как у всех мутаций проекта
    onSuccess: async () => {
      await Promise.all(
        [
          "/api/polls/{poll_id}",
          "/api/polls/{poll_id}/results",
          "/api/houses/{house_id}/polls",
        ].map((path) =>
          queryClient.invalidateQueries({ queryKey: ["get", path] }),
        ),
      );
    },
  });

  const poll = card.data;

  const toggle = (optionId: number) =>
    setChosen((current) => {
      if (current.includes(optionId)) {
        return current.filter((id) => id !== optionId);
      }

      return poll?.is_multiple ? [...current, optionId] : [optionId];
    });

  const send = () => {
    if (chosen.length > 0) {
      vote.mutate({ params, body: { option_ids: chosen } });
    }
  };

  return {
    poll,
    results: results.data,
    residency,
    chosen,
    toggle,
    isVoting: vote.isPending,
    isVoteFailed: vote.isError,
    canSend: chosen.length > 0 && !vote.isPending,
    send,
    isPending: card.isPending || results.isPending,
    isError: route === null || card.isError || results.isError,
    retry: () => {
      void card.refetch();
      void results.refetch();
    },
  };
};
