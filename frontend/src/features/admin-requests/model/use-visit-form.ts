import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { errorMessage } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { useClosingConfirmation } from "@/shared/lib/max";
import { orgParams } from "@/shared/model/session";

import {
  todayKey,
  tomorrowKey,
  visitFormConstraints as limits,
  visitWindows,
  windowLabel,
} from "../domain/visit-form";
import { refreshRequests } from "./refresh-requests";

const visitSchema = z
  .object({
    date: z
      .string()
      .min(1, "Выберите день")
      .refine((date) => date >= todayKey(), "День визита уже прошёл"),
    timeFrom: z.string().min(1, "Укажите начало"),
    timeTo: z.string().min(1, "Укажите конец"),
    minutes: z
      .number()
      .int("Окно - целое число минут")
      .min(limits.minutesMin, `Окно от ${limits.minutesMin} минут`)
      .max(limits.minutesMax, `Окно до ${limits.minutesMax} минут`),
  })
  .superRefine((draft, context) => {
    const windows = visitWindows(draft);

    if (windows.length === 0) {
      context.addIssue({
        code: "custom",
        path: ["timeTo"],
        message: "Ни одно окно не помещается: проверьте время и длину окна",
      });
    } else if (windows.length > limits.windowsMax) {
      context.addIssue({
        code: "custom",
        path: ["timeTo"],
        message: `Получается ${windows.length} окон, а предложить можно до ${limits.windowsMax}: сократите время или удлините окно`,
      });
    } else if (Date.parse(windows[0]) <= Date.now()) {
      context.addIssue({
        code: "custom",
        path: ["timeFrom"],
        message: "Первое окно уже началось: выберите время позже",
      });
    }
  });

type VisitDraft = z.infer<typeof visitSchema>;

export const useVisitForm = (requestId: number) => {
  const navigate = useNavigate();
  const form = useForm<VisitDraft>({
    resolver: zodResolver(visitSchema),
    defaultValues: {
      date: tomorrowKey(),
      timeFrom: "10:00",
      timeTo: "14:00",
      minutes: 120,
    },
  });
  useClosingConfirmation(form.formState.isDirty);
  const draft = useWatch({ control: form.control });
  const propose = rqClient.useMutation(
    "post",
    "/api/admin/requests/{request_id}/visit",
    {
      onSuccess: async () => {
        await refreshRequests();
        await navigate(-1);
      },
    },
  );
  const minutes = draft.minutes ?? 0;

  return {
    form,
    labels: visitWindows({
      date: draft.date ?? "",
      timeFrom: draft.timeFrom ?? "",
      timeTo: draft.timeTo ?? "",
      minutes,
    }).map((startsAt) => windowLabel(startsAt, minutes)),
    isSubmitting: propose.isPending,
    error:
      propose.error &&
      errorMessage(
        propose.error,
        "Не получилось отправить время. Проверьте связь и попробуйте ещё раз",
      ),
    submit: form.handleSubmit((values) =>
      propose.mutate({
        params: { ...orgParams(), path: { request_id: requestId } },
        body: {
          date: values.date,
          starts: visitWindows(values),
          minutes: values.minutes,
        },
      }),
    ),
  };
};
