// Моки до появления эндпоинтов опросов и новостей дома. Дом, квартира,
// контакты УК, активная заявка и показания приходят из API.

export type NewsKind = "alert" | "announcement";

export const HOME_MOCK = {
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
