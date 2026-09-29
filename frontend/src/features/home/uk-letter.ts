import type { HouseCard } from "@/features/house";

export type UkLetter = { subject: string; body: string };

const docDate = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

export const ukLetter = (
  org: NonNullable<HouseCard["org"]>,
  address: string,
  flat: string | null | undefined,
  text: string,
): UkLetter => ({
  subject: `Обращение жителя дома ${address}`,
  body: [
    `Кому: ${[org.name, org.address].filter(Boolean).join(", ")}`,
    `От: [ФИО], ${address}, кв. ${flat || "[номер]"}, тел. [телефон]`,
    "",
    text.trim() || "[Опишите, что случилось]",
    "",
    "Прошу ответить в срок не более 10 рабочих дней тем же способом, которым отправлено обращение (ПП РФ № 416, п. 35, 36).",
    "",
    `Дата: ${docDate.format(Date.now())}`,
  ].join("\n"),
});

export const ukMailto = (email: string, letter: UkLetter) =>
  `mailto:${email}?subject=${encodeURIComponent(letter.subject)}&body=${encodeURIComponent(letter.body)}`;
