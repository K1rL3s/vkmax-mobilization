import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { errorMessage } from "@/shared/api/errors";
import type { components } from "@/shared/api/schema/generated";
import { orgParams } from "@/shared/model/session";

import {
  isSiteAddress,
  orgFormConstraints as limits,
} from "../domain/org-form-constraints";
import { DEMO_LOCKED, type SettingsLock } from "../domain/roles";
import { useSaveSettings } from "./use-org";

export type OrgSettings = components["schemas"]["OrgSettingsResponse"];

const whole = (min: number, max: number, range: string) =>
  z
    .number({ error: "Укажите число" })
    .int("Нужно целое число")
    .min(min, range)
    .max(max, range);

const day = whole(
  limits.dayMin,
  limits.dayMax,
  `Число от ${limits.dayMin} до ${limits.dayMax}`,
);

const settingsSchema = z.object({
  meter_window_always_open: z.boolean(),
  meter_window_day_from: day,
  meter_window_day_to: day,
  group_threshold: whole(
    limits.thresholdMin,
    limits.thresholdMax,
    `От ${limits.thresholdMin} до ${limits.thresholdMax} квартир`,
  ),
  group_window_hours: whole(
    limits.windowHoursMin,
    limits.windowHoursMax,
    `От ${limits.windowHoursMin} до ${limits.windowHoursMax} часов`,
  ),
  phone: z
    .string()
    .trim()
    .min(1, "Укажите телефон для жителей")
    .max(limits.phone, `Телефон длиннее ${limits.phone} символов`),
  emergency_phone: z
    .string()
    .trim()
    .max(limits.phone, `Телефон длиннее ${limits.phone} символов`),
  email: z
    .string()
    .trim()
    .max(limits.email, `Почта длиннее ${limits.email} символов`)
    .refine(
      (value) => value === "" || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value),
      "Похоже, в адресе опечатка",
    ),
  site: z
    .string()
    .trim()
    .max(limits.site, `Ссылка длиннее ${limits.site} символов`)
    .refine(
      (value) => value === "" || isSiteAddress(value),
      "Нужен адрес вида uk-primer.ru",
    ),
  reception_note: z
    .string()
    .trim()
    .max(
      limits.receptionNote,
      `Текст длиннее ${limits.receptionNote} символов`,
    ),
});

type SettingsDraft = z.infer<typeof settingsSchema>;

const draftOf = (settings: OrgSettings): SettingsDraft => ({
  ...settings,
  reception_note: settings.reception_note ?? "",
  emergency_phone: settings.emergency_phone ?? "",
  email: settings.email ?? "",
  site: settings.site ?? "",
});

export const useSettingsForm = (settings: OrgSettings, lock: SettingsLock) => {
  const save = useSaveSettings();
  const readOnly = lock !== null;

  const form = useForm<SettingsDraft>({
    resolver: zodResolver(settingsSchema),
    mode: "onChange",
    values: draftOf(settings),
    resetOptions: { keepDirtyValues: true },
    disabled: readOnly,
  });

  const [alwaysOpen, dayFrom, dayTo, threshold, windowHours] = useWatch({
    control: form.control,
    name: [
      "meter_window_always_open",
      "meter_window_day_from",
      "meter_window_day_to",
      "group_threshold",
      "group_window_hours",
    ],
  });

  const submit = form.handleSubmit((draft) => {
    save.mutate(
      {
        params: orgParams(),
        body: {
          ...draft,
          reception_note: draft.reception_note || null,
          emergency_phone: draft.emergency_phone || null,
          email: draft.email || null,
          site: draft.site || null,
        },
      },
      {
        onSuccess: (saved) =>
          form.reset(draftOf(saved), { keepDirtyValues: false }),
      },
    );
  });

  return {
    register: form.register,
    control: form.control,
    errors: form.formState.errors,
    watched: { alwaysOpen, dayFrom, dayTo, threshold, windowHours },
    canSave: form.formState.isDirty && form.formState.isValid && !readOnly,
    hint:
      lock === "demo"
        ? DEMO_LOCKED
        : readOnly
          ? "Настройки меняют создатель и администраторы организации"
          : !form.formState.isValid
            ? "Исправьте поля, отмеченные красным"
            : form.formState.isDirty
              ? null
              : save.isSuccess
                ? "Настройки сохранены"
                : "Кнопка станет активной, когда вы что-нибудь измените",
    isSaving: save.isPending,
    saveError:
      save.isError &&
      errorMessage(
        save.error,
        "Не получилось сохранить. Проверьте связь и попробуйте ещё раз",
      ),
    submit,
  };
};
