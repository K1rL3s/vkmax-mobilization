import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";

import { gisAppealFormConstraints } from "../domain/gis-appeal-form-constraints";
import { refetchRequests } from "./use-repeat-request";

const gisAppealSchema = z.object({
  number: z
    .string()
    .trim()
    .min(1, "Впишите номер обращения")
    .max(gisAppealFormConstraints.number, "Номер слишком длинный"),
});

export const useGisAppeal = (requestId: number) => {
  const form = useForm<z.infer<typeof gisAppealSchema>>({
    resolver: zodResolver(gisAppealSchema),
    defaultValues: { number: "" },
  });
  const save = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/gis-appeal",
    { onSuccess: refetchRequests },
  );

  return {
    form,
    isPending: save.isPending,
    error: save.isError
      ? errorMessage(
          save.error,
          "Не получилось сохранить. Проверьте связь и попробуйте ещё раз",
        )
      : null,
    submit: form.handleSubmit((body) => {
      if (save.isPending) return;
      save.mutate({
        params: { ...authParams(), path: { request_id: requestId } },
        body,
      });
    }),
  };
};
