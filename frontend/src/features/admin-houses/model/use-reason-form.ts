import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { reasonFormConstraints } from "../domain/resident";

const { reasonMin, reasonMax } = reasonFormConstraints;

const reasonSchema = z.object({
  reason: z
    .string()
    .trim()
    .min(reasonMin, `Объясните причину: не меньше ${reasonMin} символов`)
    .max(reasonMax, `Причина длиннее ${reasonMax} символов`),
});

type ReasonDraft = z.infer<typeof reasonSchema>;

export const useReasonForm = (onSubmit: (reason: string) => void) => {
  const form = useForm<ReasonDraft>({
    resolver: zodResolver(reasonSchema),
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
