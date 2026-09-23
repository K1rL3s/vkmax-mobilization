import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { errorDetail } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
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
  const reply = rqClient.useMutation(
    "post",
    "/api/admin/requests/{request_id}/reply",
    {
      onSuccess: async () => {
        form.reset();
        await refreshRequests();
      },
    },
  );

  const submit = form.handleSubmit((body) => {
    if (reply.isPending) return;
    reply.mutate({
      params: { ...orgParams(), path: { request_id: requestId } },
      body,
    });
  });

  return {
    form,
    isPending: reply.isPending,
    isSuccess: reply.isSuccess,
    error: reply.isError
      ? (errorDetail(reply.error) ??
        "Не удалось отправить ответ. Попробуйте ещё раз.")
      : null,
    submit,
  };
};
