import { useState } from "react";
import { z } from "zod";

import { authParams, rqClient } from "@/shared/api/instance";
import { invalidatePaths } from "@/shared/api/query-client";
import { useRouteParams } from "@/shared/lib/router";
import { useSession } from "@/shared/model/session";

const paramsSchema = z.object({ pollId: z.coerce.number().int().positive() });

export const usePoll = () => {
  const route = useRouteParams(paramsSchema);
  const { currentResidency: residency } = useSession();
  const [chosen, setChosen] = useState<number[]>([]);

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

  const vote = rqClient.useMutation("post", "/api/polls/{poll_id}/vote", {
    onSuccess: refreshPoll,
  });

  const poll = card.data;

  const toggle = (optionId: number) =>
    setChosen((current) => {
      if (current.includes(optionId)) {
        return current.filter((id) => id !== optionId);
      }

      return poll?.is_multiple ? [...current, optionId] : [optionId];
    });

  return {
    poll,
    results: results.data,
    residency,
    chosen,
    toggle,
    isVoting: vote.isPending,
    isVoteFailed: vote.isError,
    canSend: chosen.length > 0 && !vote.isPending,
    send: () => vote.mutate({ params, body: { option_ids: chosen } }),
    isPending: route !== null && (card.isPending || results.isPending),
    isError: route === null || card.isError || results.isError,
    retry: () => {
      void card.refetch();
      void results.refetch();
    },
  };
};

export const refreshPoll = () =>
  invalidatePaths(
    "/api/polls/{poll_id}",
    "/api/polls/{poll_id}/results",
    "/api/houses/{house_id}/polls",
  );
