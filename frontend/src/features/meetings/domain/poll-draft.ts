import { z } from "zod";

import { pollFormConstraints } from "./poll-form-constraints";

// input type="date" отдаёт YYYY-MM-DD, а бэк ждёт момент времени: опрос идёт
// до конца выбранного дня, как и обещает подпись «голосование до 26 сентября»
export const endOfDay = (date: string) => new Date(`${date}T23:59:59`);

// бэк проверяет то же самое, но ошибку из ответа житель ловил бы там, где её
// видно сразу
export const pollDraftSchema = z.object({
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

export type PollDraft = z.infer<typeof pollDraftSchema>;
