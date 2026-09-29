import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { errorMessage } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import { useIdempotencyKey } from "@/shared/lib/idempotency";
import { orgParams, useSession } from "@/shared/model/session";

import { requestFormConstraints } from "../domain/request-form-constraints";
import type { AdminRequest } from "../domain/request-workflow";
import { refreshRequests } from "./refresh-requests";

const replySchema = z.object({
  text: z
    .string()
    .trim()
    .min(1, "Напишите ответ жителю")
    .max(requestFormConstraints.reply, "Сократите ответ"),
  question: z.boolean(),
});

export const useRequestReplyForm = (requestId: number) => {
  const form = useForm<z.infer<typeof replySchema>>({
    resolver: zodResolver(replySchema),
    defaultValues: { text: "", question: false },
  });
  const idempotency = useIdempotencyKey();
  const { session } = useSession();

  const reply = rqClient.useMutation(
    "post",
    "/api/admin/requests/{request_id}/reply",
    {
      onMutate: ({ body }) => {
        form.reset();
        idempotency.renew();
        queryClient.setQueriesData<AdminRequest>(
          { queryKey: ["get", "/api/admin/requests/{request_id}"] },
          (card) =>
            card?.id !== requestId
              ? card
              : {
                  ...card,
                  messages: [
                    ...card.messages,
                    {
                      created_at: new Date().toISOString(),
                      author_role: "staff",
                      author_name: session?.name ?? "Вы",
                      text: body.text,
                      is_internal: false,
                    },
                  ],
                },
        );
      },
      onError: (_error, { body }) => {
        form.reset({ text: body.text, question: body.question ?? false });
        return refreshRequests();
      },
      onSuccess: () => refreshRequests(),
    },
  );

  const submit = form.handleSubmit((body) =>
    reply.mutate({
      params: {
        header: {
          ...orgParams().header,
          "Idempotency-Key": idempotency.key,
        },
        path: { request_id: requestId },
      },
      body,
    }),
  );

  return {
    form,
    error: reply.isError
      ? errorMessage(
          reply.error,
          "Не удалось отправить ответ. Попробуйте ещё раз.",
        )
      : null,
    submit,
  };
};
