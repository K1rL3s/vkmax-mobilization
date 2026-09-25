import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { errorDetail } from "@/shared/api/errors";
import { orgParams } from "@/shared/model/session";

import { INVITABLE_ROLES } from "../domain/roles";
import { useCreateInvite } from "./use-org";

const inviteSchema = z.object({
  role: z.enum(INVITABLE_ROLES),
  expires_in_hours: z.number().int().positive(),
  max_activations: z.number().int().positive(),
});

export const useInviteForm = () => {
  const create = useCreateInvite();

  const form = useForm<z.infer<typeof inviteSchema>>({
    resolver: zodResolver(inviteSchema),
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
    reset: () => {
      create.reset();
      form.reset();
    },
  };
};
