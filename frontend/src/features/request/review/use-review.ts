import { useState } from "react";

import { authParams, rqClient } from "@/shared/api/instance";

import { refetchRequests, useRepeatRequest } from "../model/use-repeat-request";

export const COMMENT_LIMIT = 500;

export const useReview = (requestId: number) => {
  const [comment, setComment] = useState("");

  const params = { ...authParams(), path: { request_id: requestId } };

  const accept = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/accept",
    { onSuccess: refetchRequests },
  );

  const repeat = useRepeatRequest();

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
    canReject: text.length > 0 && !isSending,
    accept: () => accept.mutate({ params }),
    reject: () => repeat.mutate({ params, body: { description: text } }),
  };
};
