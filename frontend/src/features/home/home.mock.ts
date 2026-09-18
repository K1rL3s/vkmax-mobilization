// Моки до появления эндпоинтов заявок, счётчиков и опросов. Дом, квартира и
// контакты УК приходят из API.

export type NewsKind = "alert" | "announcement";

export const HOME_MOCK = {
  activeRequest: {
    number: 142,
    title: "Протечка, 2-й подъезд",
    status: "В работе",
    deadlineProgress: 0.68,
    deadlineLeft: "Осталось 5 ч 32 мин",
  },
  meters: {
    windowLeft: "Окно открыто ещё 9 дней",
  },
  poll: {
    title: "Опрос о дворе",
    deadline: "Голосование до 20.09",
  },
  news: [
    {
      id: "1",
      kind: "alert" as NewsKind,
      title: "Отключение ГВС 18.09",
      subtitle: "с 9:00 до 18:00 · вчера",
    },
    {
      id: "2",
      kind: "announcement" as NewsKind,
      title: "Плановая уборка подъездов",
      subtitle: "Объявление УК · 3 дня назад",
    },
  ],
};
