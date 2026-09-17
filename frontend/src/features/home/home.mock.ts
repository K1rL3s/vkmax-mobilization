// Моки до появления эндпоинтов кабинета жителя (shared/api/schema/main.yaml пока пустой).

export type NewsKind = "alert" | "announcement";

export const HOME_MOCK = {
  house: {
    address: "ул. Ленина, 12, кв. 45",
    city: "Казань",
    isVerified: true,
  },
  company: {
    name: "ООО «УК Уютный дом»",
    schedule: "Приём сегодня до 18:00",
    phone: "+78431234567",
  },
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
