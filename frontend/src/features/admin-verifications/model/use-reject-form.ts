import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { verificationFormConstraints } from "../domain/verification-form-constraints";

const { reasonMin, reasonMax } = verificationFormConstraints;

// бэк проверяет только непустоту, а «нет» её проходит: причина отказа -
// единственное, что получает житель
const rejectSchema = z.object({
  reason: z
    .string()
    .trim()
    .min(reasonMin, `Объясните причину: не меньше ${reasonMin} символов`)
    .max(reasonMax, `Причина длиннее ${reasonMax} символов`),
});

export type RejectDraft = z.infer<typeof rejectSchema>;

export const REJECT_PRESETS = [
  { label: "Счёт не совпал", text: "Лицевой счёт не совпал с данными УК" },
  { label: "Счёт собственника", text: "Квитанция оформлена на собственника" },
  { label: "Нет в данных УК", text: "Квартиры нет в данных УК" },
];

export const useRejectForm = (onSubmit: (reason: string) => void) => {
  const form = useForm<RejectDraft>({
    resolver: zodResolver(rejectSchema),
    mode: "onChange",
    defaultValues: { reason: "" },
  });

  return {
    control: form.control,
    register: () => form.register("reason"),
    error: form.formState.errors.reason?.message,
    canSubmit: form.formState.isValid,
    submit: form.handleSubmit((draft) => onSubmit(draft.reason)),
    usePreset: (text: string) =>
      form.setValue("reason", text, { shouldValidate: true }),
  };
};
