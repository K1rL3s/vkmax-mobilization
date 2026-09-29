import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { errorMessage } from "@/shared/api/errors";
import { orgParams } from "@/shared/model/session";

import {
  dayError,
  draftOfDay,
  gridWithDay,
  receptionFormConstraints as limits,
  slotsPerDay,
  type DayDraft,
  type ReceptionWindow,
} from "../domain/schedule";
import { useSaveReceptionWindows } from "./use-reception";

const time = z.string().regex(/^\d{2}:\d{2}$/, "Время в формате 9:00");

const whole = (min: number, max: number, message: string) =>
  z
    .number({ error: "Укажите число" })
    .int("Нужно целое число")
    .min(min, message)
    .max(max, message);

const daySchema = z.object({
  enabled: z.boolean(),
  timeFrom: time,
  timeTo: time,
  hasBreak: z.boolean(),
  breakFrom: time,
  breakTo: time,
  slotMinutes: whole(
    limits.slotMin,
    limits.slotMax,
    `От ${limits.slotMin} до ${limits.slotMax} минут`,
  ),
  capacity: whole(
    limits.capacityMin,
    limits.capacityMax,
    `От ${limits.capacityMin} до ${limits.capacityMax} жителей`,
  ),
});

export const useHoursForm = (windows: ReceptionWindow[]) => {
  const [weekday, setWeekday] = useState(0);
  const save = useSaveReceptionWindows();

  const form = useForm<DayDraft>({
    resolver: zodResolver(daySchema),
    mode: "onChange",
    values: draftOfDay(windows, weekday),
    resetOptions: { keepDirtyValues: true },
  });

  const draft = useWatch({ control: form.control }) as DayDraft;
  const spans = dayError(draft);

  const submit = form.handleSubmit((values) =>
    save.mutate(
      {
        params: orgParams(),
        body: { windows: gridWithDay(windows, weekday, values) },
      },
      {
        onSuccess: (saved) =>
          form.reset(draftOfDay(saved, weekday), { keepDirtyValues: false }),
      },
    ),
  );

  return {
    weekday,
    selectDay: (next: number) => {
      save.reset();
      setWeekday(next);
      form.reset(draftOfDay(windows, next), { keepDirtyValues: false });
    },
    register: form.register,
    errors: form.formState.errors,
    draft,
    spansError: spans,
    slots: slotsPerDay(draft),
    isTurningOff: !draft.enabled && windows.some((w) => w.weekday === weekday),
    canSave: form.formState.isDirty && form.formState.isValid && spans === null,
    isSaving: save.isPending,
    isSaved: save.isSuccess && !form.formState.isDirty,
    saveError:
      save.isError &&
      errorMessage(
        save.error,
        "Не получилось сохранить часы. Проверьте связь и попробуйте ещё раз",
      ),
    submit,
  };
};
