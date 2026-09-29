import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { useIdempotencyKey } from "@/shared/lib/idempotency";

import { messageFormConstraints } from "../domain/message-form-constraints";
import { refetchRequests } from "./use-repeat-request";

const messageSchema = z.object({
  text: z
    .string()
    .trim()
    .min(1, "Напишите сообщение для УК")
    .max(messageFormConstraints.text, "Сократите сообщение"),
});

export const useRequestReply = (requestId: number) => {
  const form = useForm<z.infer<typeof messageSchema>>({
    resolver: zodResolver(messageSchema),
    defaultValues: { text: "" },
  });
  const idempotency = useIdempotencyKey();
  const write = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/messages",
    {
      onSuccess: async () => {
        idempotency.renew();
        form.reset();
        await refetchRequests();
      },
    },
  );

  const submit = form.handleSubmit((body) => {
    if (write.isPending) return;
    write.mutate({
      params: {
        header: {
          ...authParams().header,
          "Idempotency-Key": idempotency.key,
        },
        path: { request_id: requestId },
      },
      body,
    });
  });

  return {
    form,
    isPending: write.isPending,
    error: write.isError
      ? errorMessage(
          write.error,
          "Сообщение не ушло. Проверьте связь и попробуйте ещё раз",
        )
      : null,
    submit,
  };
};
