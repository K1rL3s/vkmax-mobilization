import { z } from "zod";

export const pollFormConstraints = {
  title: 120,
  option: 80,
  description: 500,
  optionsMin: 2,
  optionsMax: 6,
};

export const endOfDay = (date: string) => new Date(`${date}T23:59:59`);

export const pollDraftSchema = z.object({
  title: z
    .string()
    .trim()
    .min(1, "Укажите, о чём опрос")
    .max(
      pollFormConstraints.title,
      `Заголовок длиннее ${pollFormConstraints.title} символов`,
    ),
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
