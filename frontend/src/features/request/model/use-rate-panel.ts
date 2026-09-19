import { useState } from "react";
import { generatePath, useNavigate } from "react-router-dom";

import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import { Routes } from "@/shared/model/routes";

import type { RequestCard } from "../domain/types";

// бэк длину отзыва не ограничивает; пятьсот знаков - предел из макета
export const FEEDBACK_LIMIT = 500;

const failedAction = (rating: boolean, repeat: boolean) => {
  if (repeat) {
    return "repeat";
  }

  return rating ? "rate" : null;
};

// поле в макете одно на обе кнопки: к оценке текст уходит отзывом, к
// «Сделано плохо» - описанием повторной заявки
export const useRatePanel = (request: RequestCard) => {
  const navigate = useNavigate();
  const [rating, setRating] = useState(0);
  const [feedback, setFeedback] = useState("");

  const params = { ...authParams(), path: { request_id: request.id } };

  const refetchRequests = async () => {
    await queryClient.invalidateQueries({
      queryKey: ["get", "/api/requests/{request_id}"],
    });
    await queryClient.invalidateQueries({
      queryKey: ["get", "/api/requests"],
    });
  };

  const rate = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/rating",
    { onSuccess: refetchRequests },
  );

  const repeat = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/repeat",
    {
      onSuccess: async (created) => {
        await refetchRequests();
        // исходная заявка уходит из истории: назад из повторной житель
        // возвращается в ленту, как из мастера
        await navigate(
          generatePath(Routes.REQUEST, { requestId: String(created.id) }),
          { replace: true },
        );
      },
    },
  );

  // у оценённой заявки поля уже нет: описанием повтора становится отзыв,
  // который житель оставил к оценке
  const text = feedback.trim() || (request.feedback ?? "").trim();
  const isSending = rate.isPending || repeat.isPending || repeat.isSuccess;

  return {
    rating,
    setRating,
    feedback,
    setFeedback: (next: string) => setFeedback(next.slice(0, FEEDBACK_LIMIT)),
    isRating: rate.isPending || rate.isSuccess,
    isRepeating: repeat.isPending || repeat.isSuccess,
    failed: failedAction(rate.isError, repeat.isError),
    canRate: rating > 0 && !isSending,
    canRepeat: text.length > 0 && !isSending,
    rate: () => {
      if (rating > 0) {
        rate.mutate({ params, body: { rating, feedback: text || null } });
      }
    },
    repeat: () => {
      if (text.length > 0) {
        repeat.mutate({ params, body: { description: text } });
      }
    },
  };
};
