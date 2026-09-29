import { useState } from "react";

import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";

import type { RequestCard } from "../domain/types";
import { refetchRequests, useRepeatRequest } from "./use-repeat-request";

export const FEEDBACK_LIMIT = 500;

export const useRatePanel = (request: RequestCard) => {
  const [rating, setRating] = useState(0);
  const [feedback, setFeedback] = useState("");

  const params = { ...authParams(), path: { request_id: request.id } };

  const rate = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/rating",
    { onSuccess: refetchRequests },
  );

  const repeat = useRepeatRequest();

  const text = feedback.trim() || (request.feedback ?? "").trim();
  const isSending = rate.isPending || repeat.isPending || repeat.isSuccess;

  return {
    rating,
    setRating,
    feedback,
    setFeedback: (next: string) => setFeedback(next.slice(0, FEEDBACK_LIMIT)),
    isRating: rate.isPending || rate.isSuccess,
    isRepeating: repeat.isPending || repeat.isSuccess,
    repeatError:
      repeat.error &&
      errorMessage(
        repeat.error,
        "Повторная заявка не создалась. Проверьте связь и попробуйте ещё раз",
      ),
    rateError:
      rate.error &&
      errorMessage(
        rate.error,
        "Оценка не ушла. Проверьте связь и попробуйте ещё раз",
      ),
    canRate: rating > 0 && !isSending,
    canRepeat: text.length > 0 && !isSending,
    rate: () =>
      rate.mutate({ params, body: { rating, feedback: text || null } }),
    repeat: () => repeat.send(request.id, text),
  };
};
