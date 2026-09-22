import { zodResolver } from "@hookform/resolvers/zod";
import { useFieldArray, useForm } from "react-hook-form";
import { generatePath, useNavigate } from "react-router-dom";
import { z } from "zod";

import {
  endOfDay,
  pollDraftSchema,
  pollFormConstraints,
} from "@/features/meetings";
import { errorDetail } from "@/shared/api/errors";
import { rqClient } from "@/shared/api/instance";
import { Routes } from "@/shared/model/routes";
import { orgParams } from "@/shared/model/session";

const draftSchema = pollDraftSchema.extend({
  houseId: z.string().min(1, "Выберите дом"),
  isMultiple: z.boolean(),
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
      endsAt: "",
    },
  });

  const options = useFieldArray({ control: form.control, name: "options" });

  const create = rqClient.useMutation("post", "/api/admin/polls", {
    // форма из истории уходит: назад с опроса сотрудник попадает в список
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
    retryHouses: () => void houses.refetch(),
    register: form.register,
    // ошибка «варианты повторяются» живёт на массиве, а RHF перепроверяет
    // только изменённое поле
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
    // сегодняшний день ещё идёт, поэтому он допустим
    minDate: new Date().toISOString().slice(0, 10),
    isSubmitting: create.isPending,
    // бэк отвечает понятным текстом на 400, 404 и 409; без него это связь
    submitError:
      create.isError &&
      (errorDetail(create.error) ??
        "Опрос не создался. Проверьте связь и попробуйте ещё раз."),
    submit: form.handleSubmit((draft) => {
      if (create.isPending) {
        return;
      }

      create.mutate({
        params: orgParams(),
        body: {
          house_id: Number(draft.houseId),
          title: draft.title,
          description: draft.description.trim() || null,
          options: draft.options.map(({ text }) => text),
          ends_at: endOfDay(draft.endsAt).toISOString(),
          is_multiple: draft.isMultiple,
        },
      });
    }),
  };
};
