import { useState } from "react";

import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";

// столько же, сколько отзыв к оценке: житель пишет в то же окно мыслей
export const COMMENT_LIMIT = 500;

export const useReview = (requestId: number) => {
  const [comment, setComment] = useState("");

  const review = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/review",
    {
      onSuccess: async () => {
        await queryClient.invalidateQueries({
          queryKey: ["get", "/api/requests/{request_id}"],
        });
        await queryClient.invalidateQueries({
          queryKey: ["get", "/api/requests"],
        });
      },
    },
  );

  const params = { ...authParams(), path: { request_id: requestId } };
  const text = comment.trim();
  const isSending = review.isPending || review.isSuccess;

  return {
    comment,
    setComment: (next: string) => setComment(next.slice(0, COMMENT_LIMIT)),
    isAccepting: review.isPending && review.variables?.body.accepted === true,
    isRejecting: review.isPending && review.variables?.body.accepted === false,
    isFailed: review.isError,
    canAccept: !isSending,
    // без объяснения возвращать работу нельзя: исполнителю нечего исправлять
    canReject: text.length > 0 && !isSending,
    accept: () =>
      review.mutate({
        params,
        body: { accepted: true, comment: text || null },
      }),
    reject: () => {
      if (text.length > 0) {
        review.mutate({ params, body: { accepted: false, comment: text } });
      }
    },
  };
};
