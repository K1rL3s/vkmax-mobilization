import { useState } from "react";
import { generatePath, useNavigate } from "react-router-dom";

import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import { Routes } from "@/shared/model/routes";

// столько же, сколько отзыв к оценке: житель пишет в то же окно мыслей
export const COMMENT_LIMIT = 500;

// приёмка - две разные ручки: принятая работа закрывает заявку, непринятая
// уходит повтором, который заодно закрывает исходную
export const useReview = (requestId: number) => {
  const navigate = useNavigate();
  const [comment, setComment] = useState("");

  const params = { ...authParams(), path: { request_id: requestId } };

  const refetchRequests = async () => {
    await queryClient.invalidateQueries({
      queryKey: ["get", "/api/requests/{request_id}"],
    });
    await queryClient.invalidateQueries({
      queryKey: ["get", "/api/requests"],
    });
  };

  const accept = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/accept",
    { onSuccess: refetchRequests },
  );

  const repeat = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/repeat",
    {
      onSuccess: async (created) => {
        await refetchRequests();
        // исходная заявка закрыта отказом: назад из повторной житель
        // возвращается в ленту, как из мастера
        await navigate(
          generatePath(Routes.REQUEST, { requestId: String(created.id) }),
          { replace: true },
        );
      },
    },
  );

  const text = comment.trim();
  const isSending =
    accept.isPending ||
    accept.isSuccess ||
    repeat.isPending ||
    repeat.isSuccess;

  return {
    comment,
    setComment: (next: string) => setComment(next.slice(0, COMMENT_LIMIT)),
    isAccepting: accept.isPending || accept.isSuccess,
    isRejecting: repeat.isPending || repeat.isSuccess,
    isFailed: accept.isError || repeat.isError,
    canAccept: !isSending,
    // без объяснения отказ не уходит: бэк отбивает пустое описание, а
    // исполнителю нечего исправлять
    canReject: text.length > 0 && !isSending,
    accept: () => accept.mutate({ params }),
    reject: () => {
      if (text.length > 0) {
        repeat.mutate({ params, body: { description: text } });
      }
    },
  };
};
