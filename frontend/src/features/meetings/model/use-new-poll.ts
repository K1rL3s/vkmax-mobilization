import { zodResolver } from "@hookform/resolvers/zod";
import { useFieldArray, useForm } from "react-hook-form";
import { generatePath, useNavigate } from "react-router-dom";
import { z } from "zod";

import { authParams, rqClient } from "@/shared/api/instance";
import { queryClient } from "@/shared/api/query-client";
import { Routes } from "@/shared/model/routes";
import { useSession } from "@/shared/model/session";

import { pollFormConstraints } from "../domain/poll-form-constraints";

// input type="date" отдаёт YYYY-MM-DD, а бэк ждёт момент времени: опрос идёт
// до конца выбранного дня, как и обещает подпись «голосование до 26 сентября»
const endOfDay = (date: string) => new Date(`${date}T23:59:59`);

// бэк проверяет то же самое, но ошибку из ответа житель ловил бы там, где её
// видно сразу
const draftSchema = z.object({
  title: z
    .string()
    .trim()
    .min(1, "Укажите, о чём опрос")
    .max(
      pollFormConstraints.title,
      `Заголовок длиннее ${pollFormConstraints.title} символов`,
    ),
  // длину набора держат кнопки: убрать ниже двух и добавить выше шести
  // нельзя, поэтому схема проверяет только сами варианты. useFieldArray
  // работает с объектами, а не со строками, отсюда { text }
  options: z
    .array(
      z.object({
        text: z
          .string()
          .trim()
          .min(1, "Заполните вариант")
          .max(
            pollFormConstraints.option,
            `Вариант длиннее ${pollFormConstraints.option} символов`,
          ),
      }),
    )
    // пустые варианты сравнивать незачем: о них уже сказано у самих полей
    .refine((options) => {
      const filled = options.map(({ text }) => text).filter(Boolean);

      return new Set(filled).size === filled.length;
    }, "Варианты ответа не должны повторяться"),
  endsAt: z
    .string()
    .min(1, "Выберите дату окончания")
    .refine(
      (value) => !Number.isNaN(endOfDay(value).getTime()),
      "Выберите дату окончания",
    )
    .refine(
      (value) => endOfDay(value) > new Date(),
      "Дата окончания должна быть в будущем",
    ),
  description: z
    .string()
    .max(
      pollFormConstraints.description,
      `Описание длиннее ${pollFormConstraints.description} символов`,
    ),
});

export type PollDraft = z.infer<typeof draftSchema>;

export const useNewPoll = () => {
  const navigate = useNavigate();
  const { currentResidency: residency } = useSession();

  const form = useForm<PollDraft>({
    resolver: zodResolver(draftSchema),
    // ошибка поля появляется по мере ввода, а не после первой отправки
    mode: "onChange",
    defaultValues: {
      title: "",
      description: "",
      endsAt: "",
      options: [{ text: "" }, { text: "" }],
    },
  });

  const options = useFieldArray({ control: form.control, name: "options" });

  const create = rqClient.useMutation("post", "/api/houses/{house_id}/polls", {
    onSuccess: async (poll) => {
      await queryClient.invalidateQueries({
        queryKey: ["get", "/api/houses/{house_id}/polls"],
      });
      // форма из истории уходит: назад с карточки председатель возвращается
      // во вкладку, а не в заполненные поля
      await navigate(
        generatePath(Routes.MEETING, { pollId: String(poll.id) }),
        {
          replace: true,
        },
      );
    },
  });

  const errors = form.formState.errors;

  const submit = form.handleSubmit((draft) => {
    if (residency === undefined) {
      return;
    }

    create.mutate({
      params: { ...authParams(), path: { house_id: residency.house_id } },
      body: {
        title: draft.title,
        description: draft.description.trim() || null,
        options: draft.options.map(({ text }) => text),
        ends_at: endOfDay(draft.endsAt).toISOString(),
        // мультивыборные опросы фронт читает, но создаёт только
        // одновыборные: переключатель пришлось бы объяснять
        is_multiple: false,
      },
    });
  });

  return {
    isChairman: residency?.is_chairman === true,
    register: form.register,
    // ошибка набора живёт на самом массиве, а RHF обновляет ошибку только
    // изменённого поля: без пересчёта «варианты не должны повторяться» висит
    // до следующей отправки
    registerOption: (index: number) =>
      form.register(`options.${index}.text`, {
        onChange: () => void form.trigger("options"),
      }),
    errors,
    // ошибка набора вариантов принадлежит секции, а не полю
    optionsError: errors.options?.root?.message ?? errors.options?.message,
    options: options.fields,
    addOption: () => options.append({ text: "" }),
    removeOption: (index: number) => options.remove(index),
    canAddOption: options.fields.length < pollFormConstraints.optionsMax,
    canRemoveOption: options.fields.length > pollFormConstraints.optionsMin,
    control: form.control,
    // сегодняшний день ещё идёт, поэтому он остаётся допустимым
    minDate: new Date().toISOString().slice(0, 10),
    // кнопка активна всегда: ошибку набора вариантов RHF показывает только
    // после полной проверки, то есть по нажатию, и мёртвая кнопка не дала бы
    // жителю её увидеть
    canSubmit: !create.isPending,
    isSubmitting: create.isPending,
    isFailed: create.isError,
    submit,
  };
};
