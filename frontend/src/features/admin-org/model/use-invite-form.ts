import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { errorDetail } from "@/shared/api/errors";
import { orgParams } from "@/shared/model/session";

import { useCreateInvite } from "./use-org";

// бэк требует только «больше нуля» и сверху не ограничивает: выбор из
// готовых значений держит ссылки короткоживущими
export const LIFETIMES = [
  { value: 24, label: "1 день" },
  { value: 72, label: "3 дня" },
  { value: 168, label: "Неделя" },
  { value: 720, label: "30 дней" },
];

export const ACTIVATIONS = [1, 3, 5, 10];

const inviteSchema = z.object({
  role: z.enum(["admin", "employee", "executor"]),
  expires_in_hours: z.number().int().positive(),
  max_activations: z.number().int().positive(),
});

type InviteDraft = z.infer<typeof inviteSchema>;

export const useInviteForm = () => {
  const create = useCreateInvite();

  const form = useForm<InviteDraft>({
    resolver: zodResolver(inviteSchema),
    // сотрудника вправе пригласить и создатель, и администратор
    defaultValues: {
      role: "employee",
      expires_in_hours: 72,
      max_activations: 1,
    },
  });

  const [role, hours, activations] = useWatch({
    control: form.control,
    name: ["role", "expires_in_hours", "max_activations"],
  });

  return {
    values: { role, hours, activations },
    setValue: form.setValue,
    submit: form.handleSubmit((draft) =>
      create.mutate({ params: orgParams(), body: draft }),
    ),
    created: create.data,
    isPending: create.isPending,
    error:
      create.isError &&
      (errorDetail(create.error) ??
        "Не получилось создать ссылку. Проверьте связь и попробуйте ещё раз"),
    // следующее открытие начинается с выбора, а не с прошлой ссылки
    reset: () => {
      create.reset();
      form.reset();
    },
  };
};
