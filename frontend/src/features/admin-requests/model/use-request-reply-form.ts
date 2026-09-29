import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { errorMessage } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { useIdempotencyKey } from "@/shared/lib/idempotency";
import { orgParams } from "@/shared/model/session";

import { requestFormConstraints } from "../domain/request-form-constraints";
import { refreshRequests } from "./refresh-requests";

const replySchema = z.object({
  text: z
    .string()
    .trim()
    .min(1, "Напишите ответ жителю")
    .max(requestFormConstraints.reply, "Сократите ответ"),
});

export const useRequestReplyForm = (requestId: number) => {
  const form = useForm<z.infer<typeof replySchema>>({
    resolver: zodResolver(replySchema),
    defaultValues: { text: "" },
  });
  const idempotency = useIdempotencyKey();
  const reply = rqClient.useMutation(
    "post",
    "/api/admin/requests/{request_id}/reply",
    {
      onSuccess: async () => {
        idempotency.renew();
        form.reset();
        await refreshRequests();
      },
    },
  );

  const submit = form.handleSubmit((body) => {
    if (reply.isPending) return;
    reply.mutate({
      params: {
        header: {
          ...orgParams().header,
          "Idempotency-Key": idempotency.key,
        },
        path: { request_id: requestId },
      },
      body,
    });
  });

  return {
    form,
    isPending: reply.isPending,
    isSuccess: reply.isSuccess,
    error: reply.isError
      ? errorMessage(
          reply.error,
          "Не удалось отправить ответ. Попробуйте ещё раз.",
        )
      : null,
    submit,
  };
};
