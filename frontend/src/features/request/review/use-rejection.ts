import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { errorMessage } from "@/shared/api/errors";
import { useAttachments } from "@/shared/ui/attachment-picker";
import { rejectionFormConstraints } from "../domain/rejection-form-constraints";
import type { RequestCard } from "../domain/types";

import { useRepeatRequest } from "../model/use-repeat-request";

const rejectionSchema = z.object({
  comment: z
    .string()
    .trim()
    .min(1, "Опишите, что не так")
    .max(rejectionFormConstraints.comment, "Сократите описание"),
});

export const useRejection = (
  request: Pick<RequestCard, "id" | "rejection_needs_photo">,
  action: string,
) => {
  const form = useForm<z.infer<typeof rejectionSchema>>({
    resolver: zodResolver(rejectionSchema),
    mode: "onChange",
    defaultValues: { comment: "" },
  });
  const attachments = useAttachments();
  const repeat = useRepeatRequest();

  const hasText = form.formState.isValid;
  const hasProof =
    attachments.names.length > 0 || !request.rejection_needs_photo;
  const isSending = repeat.isPending || repeat.isSuccess;

  return {
    form,
    attachments,
    needsPhoto: request.rejection_needs_photo,
    isSending,
    canSend: hasText && hasProof && !attachments.isUploading && !isSending,
    missing: isSending
      ? null
      : rejectionMissing(action, hasText, hasProof, attachments.isUploading),
    error:
      repeat.error &&
      errorMessage(
        repeat.error,
        "Ответ не ушёл. Проверьте связь и попробуйте ещё раз",
      ),
    send: form.handleSubmit(({ comment }) =>
      repeat.send(request.id, comment, attachments.names),
    ),
  };
};

export type Rejection = ReturnType<typeof useRejection>;

const rejectionMissing = (
  action: string,
  hasText: boolean,
  hasProof: boolean,
  isUploading: boolean,
): string | null => {
  if (!hasText && !hasProof) {
    return `Для ${action} опишите, что не так, и приложите фото`;
  }

  if (!hasText) {
    return `Для ${action} опишите, что не так`;
  }

  if (!hasProof) {
    return `Для ${action} приложите фото`;
  }

  return isUploading ? "Дождитесь загрузки вложений" : null;
};
