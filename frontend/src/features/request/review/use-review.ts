import { useState } from "react";

import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { useAttachments } from "@/shared/ui/attachment-picker";
import type { RequestCard } from "../domain/types";

import { refetchRequests, useRepeatRequest } from "../model/use-repeat-request";

export const COMMENT_LIMIT = 500;

export const useReview = (request: RequestCard) => {
  const [comment, setComment] = useState("");
  const attachments = useAttachments();

  const params = { ...authParams(), path: { request_id: request.id } };

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
  const hasProof =
    attachments.names.length > 0 || !request.rejection_needs_photo;

  return {
    comment,
    setComment: (next: string) => setComment(next.slice(0, COMMENT_LIMIT)),
    attachments,
    isAccepting: accept.isPending || accept.isSuccess,
    isRejecting: repeat.isPending || repeat.isSuccess,
    error:
      (accept.error ?? repeat.error) &&
      errorMessage(
        accept.error ?? repeat.error,
        "Ответ не ушёл. Проверьте связь и попробуйте ещё раз",
      ),
    canAccept: !isSending,
    canReject:
      text.length > 0 && hasProof && !attachments.isUploading && !isSending,
    rejectMissing: isSending
      ? null
      : rejectMissing(text.length > 0, hasProof, attachments.isUploading),
    accept: () => accept.mutate({ params }),
    reject: () => repeat.send(request.id, text, attachments.names),
  };
};

const rejectMissing = (
  hasText: boolean,
  hasProof: boolean,
  isUploading: boolean,
): string | null => {
  if (!hasText && !hasProof) {
    return "Для «Сделано плохо» опишите, что не так, и приложите фото";
  }

  if (!hasText) {
    return "Для «Сделано плохо» опишите, что не так";
  }

  if (!hasProof) {
    return "Для «Сделано плохо» приложите фото";
  }

  return isUploading ? "Дождитесь загрузки вложений" : null;
};
