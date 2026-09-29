import { zodResolver } from "@hookform/resolvers/zod";
import { useFieldArray, useForm } from "react-hook-form";
import { generatePath, useNavigate } from "react-router-dom";
import { z } from "zod";

import {
  endOfDay,
  pollDraftSchema,
  pollFormConstraints,
} from "@/features/meetings";
import { errorMessage } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { Routes } from "@/shared/model/routes";
import { useIdempotencyKey } from "@/shared/lib/idempotency";
import { orgParams } from "@/shared/model/session";

const draftSchema = pollDraftSchema.extend({
  houseId: z.string().min(1, "Выберите дом"),
  isMultiple: z.boolean(),
  notifyResidents: z.boolean(),
});

export type AdminPollDraft = z.infer<typeof draftSchema>;

export const useAdminPollForm = () => {
  const navigate = useNavigate();

  const houses = rqClient.useQuery("get", "/api/admin/houses", {
    params: { ...orgParams(), query: { limit: 100 } },
  });

  const form = useForm<AdminPollDraft>({
    resolver: zodResolver(draftSchema),
    mode: "onChange",
    defaultValues: {
      houseId: "",
      title: "",
      description: "",
      options: [{ text: "" }, { text: "" }],
      isMultiple: false,
      notifyResidents: false,
      endsAt: "",
    },
  });

  const options = useFieldArray({ control: form.control, name: "options" });

  const idempotency = useIdempotencyKey();
  const create = rqClient.useMutation("post", "/api/admin/polls", {
    onSuccess: (poll) =>
      navigate(generatePath(Routes.ADMIN_POLL, { pollId: String(poll.id) }), {
        replace: true,
      }),
  });

  const errors = form.formState.errors;

  return {
    houses: houses.data?.items ?? [],
    isHousesPending: houses.isPending,
    isHousesError: houses.isError,
    housesError: houses.error,
    retryHouses: () => void houses.refetch(),
    register: form.register,
    registerOption: (index: number) =>
      form.register(`options.${index}.text`, {
        onChange: () => void form.trigger("options"),
      }),
    control: form.control,
    errors,
    optionsError: errors.options?.root?.message ?? errors.options?.message,
    options: options.fields,
    addOption: () => options.append({ text: "" }),
    removeOption: (index: number) => options.remove(index),
    canAddOption: options.fields.length < pollFormConstraints.optionsMax,
    canRemoveOption: options.fields.length > pollFormConstraints.optionsMin,
    isSubmitting: create.isPending,
    submitError:
      create.isError &&
      errorMessage(
        create.error,
        "Опрос не создался. Проверьте связь и попробуйте ещё раз.",
      ),
    submit: form.handleSubmit((draft) =>
      create.mutate({
        params: {
          header: {
            ...orgParams().header,
            "Idempotency-Key": idempotency.key,
          },
        },
        body: {
          house_id: Number(draft.houseId),
          title: draft.title,
          description: draft.description.trim() || null,
          options: draft.options.map(({ text }) => text),
          ends_at: endOfDay(draft.endsAt).toISOString(),
          is_multiple: draft.isMultiple,
          notify_residents: draft.notifyResidents,
        },
      }),
    ),
  };
};
