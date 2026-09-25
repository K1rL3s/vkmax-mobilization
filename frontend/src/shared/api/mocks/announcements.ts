import type { components } from "../schema/generated";

import { endpoint, forbidden, houseOf, ok, page } from "./reply";
import { findHouse, minutes } from "./state";

type Schemas = components["schemas"];

type Seed = { daysAgo: number; at: string; text: string; urgent?: boolean };

const SEEDS: Seed[] = [
  {
    daysAgo: 0,
    at: "now",
    urgent: true,
    text: "Отключение горячей воды 24 сентября с 9:00 до 18:00: ремонт на теплотрассе. Наберите воду заранее",
  },
  {
    daysAgo: 1,
    at: "18:40",
    text: "Завтра с 10:00 до 13:00 уборка придомовой территории. Просим убрать машины с парковки у второго подъезда",
  },
  {
    daysAgo: 3,
    at: "11:05",
    text: "Уважаемые жители!\nВ четверг проведём осмотр чердака и кровли перед зимой.\nДоступ на технический этаж понадобится с 10:00 до 16:00, ключи будут у дворника",
  },
  {
    daysAgo: 5,
    at: "09:30",
    text: "Показания счётчиков воды и электричества за сентябрь принимаются до 25 числа. Передать их можно в разделе «Показания»",
  },
  {
    daysAgo: 6,
    at: "16:20",
    text: "Лифт во втором подъезде снова работает, спасибо за терпение",
  },
  {
    daysAgo: 8,
    at: "08:15",
    text: "Во втором подъезде остановлен лифт: диспетчер фиксирует неисправность привода. Мастер приедет до 14:00",
    urgent: true,
  },
  {
    daysAgo: 10,
    at: "12:00",
    text: "С 1 октября начинается отопительный сезон. Если к 5 октября батареи останутся холодными, оставьте заявку в приложении, и мастер проверит стояк",
  },
  {
    daysAgo: 12,
    at: "10:45",
    text: "Пятнадцатого числа будет дезинсекция подвала. Запах сохранится около суток, окна на первом этаже лучше держать закрытыми",
  },
  {
    daysAgo: 15,
    at: "14:10",
    text: "Установили новые почтовые ящики в первом подъезде. Ключи можно получить у консьержа, при себе иметь паспорт",
  },
  {
    daysAgo: 18,
    at: "17:30",
    text: "Напоминаем: крупногабаритный мусор выносится только на площадку у въезда, вывоз по средам",
  },
  {
    daysAgo: 21,
    at: "09:00",
    text: "Общее собрание собственников пройдёт в заочной форме до конца месяца. Проголосовать можно в разделе «Собрания», бланки также лежат у консьержа.\n\nНа повестке:\n1. Замена входных дверей в подъездах.\n2. Установка шлагбаума на въезде во двор.\n3. Выбор подрядчика на ремонт отмостки.\n\nПодробности и сметы - на сайте управляющей компании: https://example.org/sobranie/2026/sentyabr/povestka-i-smety-po-vsem-voprosam",
  },
  {
    daysAgo: 24,
    at: "13:25",
    text: "Покраска перил и почтовых ящиков на лестничных клетках продлится до пятницы",
  },
  {
    daysAgo: 27,
    at: "15:50",
    text: "Во дворе высадили шесть лип и кусты сирени. Просим не парковаться на газоне",
  },
  {
    daysAgo: 30,
    at: "11:40",
    text: "Промывка системы отопления назначена на следующую неделю, возможен шум в трубах",
  },
  {
    daysAgo: 34,
    at: "10:00",
    text: "Поверка счётчиков горячей воды: у части квартир срок истекает в этом году. Проверьте дату в разделе «Показания»",
  },
  {
    daysAgo: 38,
    at: "19:05",
    text: "На детской площадке заменили покрытие и качели",
  },
  {
    daysAgo: 42,
    at: "08:50",
    text: "Сотрудники УК не ходят по квартирам с проверкой газовых плит без предварительного объявления. Не пускайте посторонних",
  },
  {
    daysAgo: 47,
    at: "12:30",
    text: "Изменились часы приёма УК: вторник и четверг с 15:00 до 19:00",
  },
  {
    daysAgo: 53,
    at: "16:00",
    text: "Прочистили ливнёвку у третьего подъезда, лужа у входа больше не собирается",
  },
  {
    daysAgo: 60,
    at: "09:15",
    text: "Плановое отключение холодной воды 12 августа с 10:00 до 14:00",
  },
  {
    daysAgo: 70,
    at: "14:45",
    text: "Во дворе появились контейнеры для раздельного сбора пластика и бумаги",
  },
  {
    daysAgo: 85,
    at: "10:20",
    text: "Помыли окна и светильники в подъездах",
  },
  {
    daysAgo: 300,
    at: "11:00",
    text: "Поздравляем с Новым годом! Дежурный диспетчер УК работает все праздники",
  },
];

const createdAt = ({ daysAgo, at }: Seed): string => {
  if (at === "now") {
    return minutes(-5);
  }

  const [hours, minutesPart] = at.split(":").map(Number);
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);
  date.setHours(hours, minutesPart, 0, 0);

  return date.toISOString();
};

export const announcementsConfigs = [
  endpoint("get", "/announcements", (request) => {
    const houseId = houseOf(request);

    if (houseId === null) {
      return forbidden("Укажите X-House-Id");
    }

    const orgName = findHouse(houseId)?.org?.name ?? null;

    return ok(
      page(
        houseId === 1
          ? SEEDS.map((seed, index) => ({
              id: SEEDS.length - index,
              created_at: createdAt(seed),
              text: seed.text,
              urgent: seed.urgent ?? false,
              org_name: orgName,
              house_ids: [houseId],
              channels: ["chat" as const],
              recipients_count: 0,
            }))
          : [],
        request.query,
      ) satisfies Schemas["Page_AnnouncementItem_"],
    );
  }),
];
