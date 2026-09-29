import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";

import { CANCEL_REASONS, cancelFormConstraints } from "../domain/cancel";
import type { CancelReason } from "../domain/types";
import { refetchRequests } from "./use-repeat-request";

const cancelSchema = z
  .object({
    reason: z.enum(
      Object.keys(CANCEL_REASONS) as [CancelReason, ...CancelReason[]],
    ),
    comment: z
      .string()
      .trim()
      .max(cancelFormConstraints.comment, "Сократите комментарий"),
  })
  .refine((draft) => draft.reason !== "other" || draft.comment.length > 0, {
    path: ["comment"],
    message: "Расскажите, почему отменяете заявку",
  });

export const useCancelRequest = (requestId: number, onDone: () => void) => {
  const form = useForm<z.infer<typeof cancelSchema>>({
    resolver: zodResolver(cancelSchema),
    mode: "onChange",
    defaultValues: { comment: "" },
  });
  const reason = useWatch({ control: form.control, name: "reason" });
  const cancel = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/cancel",
    {
      onSuccess: async () => {
        onDone();
        await refetchRequests();
      },
    },
  );

  return {
    form,
    isOther: reason === "other",
    isPending: cancel.isPending,
    canSubmit: form.formState.isValid && !cancel.isPending,
    commentError: form.formState.errors.comment?.message,
    error:
      cancel.error &&
      errorMessage(
        cancel.error,
        "Заявка не отменилась. Проверьте связь и попробуйте ещё раз",
      ),
    submit: form.handleSubmit(({ reason: picked, comment }) =>
      cancel.mutate({
        params: { ...authParams(), path: { request_id: requestId } },
        body: { reason: picked, comment: comment || null },
      }),
    ),
  };
};
