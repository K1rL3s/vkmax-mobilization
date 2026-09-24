import type { components } from "../../schema/generated";

type Schemas = components["schemas"];

import { days, minutes } from "./time";

export type MockRequest = {
  id: number;
  house_id: number;
  created_at: string;
  category: Schemas["RequestCategory"];
  description: string;
  status: Schemas["RequestStatus"];
  channel: Schemas["RequestChannel"];
  has_photos: boolean;
  group_size: number;
  group_id: number | null;
  flat_number: string | null;
  executor_name: string | null;
  rating: number | null;
  feedback: string | null;
  has_result_photos: boolean;
  deadline_at: string | null;
  parent_request_id: number | null;
  completion_reason: Schemas["RequestCompletionReason"] | null;
  photo_names: string[];
  messages: { after_minutes: number; text: string }[];
};

export const request = (
  fields: Pick<
    MockRequest,
    "id" | "category" | "description" | "status" | "created_at"
  > &
    Partial<MockRequest>,
): MockRequest => {
  const item: MockRequest = {
    house_id: 1,
    channel: "miniapp",
    has_photos: true,
    group_size: 1,
    group_id: null,
    flat_number: "45",
    executor_name: null,
    rating: null,
    feedback: null,
    has_result_photos: false,
    deadline_at: null,
    parent_request_id: null,
    completion_reason: null,
    photo_names: [],
    messages: [],
    ...fields,
  };

  // у завершённой заявки причина есть всегда; демо-данные называют её только
  // там, где она не «житель принял»
  if (item.status === "done" && item.completion_reason === null) {
    item.completion_reason = "resident_accepted";
  }

  return item;
};

// демо-лента повторяет макет; сроки считаются от «сейчас», иначе заявки
// протухают вместе с датой, на которую их написали
export const SEED_REQUESTS: MockRequest[] = [
  request({
    id: 145,
    category: "water_supply",
    description: "Нет холодной воды",
    status: "accepted",
    created_at: days(-2),
    deadline_at: minutes(20 * 60),
    messages: [
      {
        after_minutes: 26,
        text: "Авария на водоводе, работы ведёт Водоканал. Передали вашу заявку, следим за сроками.",
      },
    ],
  }),
  request({
    id: 142,
    category: "leak",
    description: "Протечка, 2-й подъезд",
    status: "in_progress",
    created_at: days(-3),
    deadline_at: minutes(332),
    group_size: 7,
    group_id: 12,
    executor_name: "Сантехник Алексей Петров",
    messages: [
      {
        after_minutes: 18,
        text: "Заявку приняли, передаём сантехнику. Напишем, когда назначим время.",
      },
      {
        after_minutes: 104,
        text: "Сантехник придёт сегодня до 16:00. Обеспечьте, пожалуйста, доступ в квартиру.",
      },
    ],
  }),
  request({
    id: 141,
    category: "electricity",
    description: "Снова не горит свет на 5 этаже",
    status: "in_progress",
    created_at: days(-1),
    deadline_at: minutes(10 * 60),
    parent_request_id: 131,
  }),
  request({
    id: 139,
    category: "heating",
    description: "Холодные батареи в квартире",
    status: "in_progress",
    created_at: days(-5),
    deadline_at: minutes(-190),
  }),
  request({
    id: 137,
    category: "elevator",
    description: "Не закрывается дверь лифта",
    status: "on_review",
    // приёмка должна идти прямо сейчас: от шага «На приёмке» считается
    // автозакрытие, и с давней датой счётчик показывал бы прошедшее
    created_at: days(-2),
    deadline_at: days(-1),
    executor_name: "Механик Ильдар Гафуров",
    has_result_photos: true,
    messages: [
      {
        after_minutes: 1330,
        text: "Заменили доводчик двери. Посмотрите, пожалуйста, и примите работу.",
      },
    ],
  }),
  request({
    id: 133,
    category: "garbage",
    description: "Не вывезли мусор с площадки",
    status: "new",
    created_at: minutes(-120),
    deadline_at: minutes(22 * 60),
    has_photos: false,
  }),
  request({
    id: 131,
    category: "electricity",
    description: "Не горит свет на 5 этаже",
    status: "done",
    created_at: days(-16),
    executor_name: "Электрик Олег Смирнов",
    messages: [
      {
        after_minutes: 1425,
        text: "Заменили лампу и датчик движения на 5 этаже.",
      },
    ],
  }),
  request({
    id: 128,
    category: "entrance",
    description: "Разбито стекло в подъезде",
    status: "done",
    created_at: days(-20),
    // житель до приёмки не дошёл: такую заявку оценить уже нельзя
    completion_reason: "auto_closed",
  }),
  request({
    id: 126,
    category: "yard",
    description: "Яма у детской площадки",
    status: "done",
    created_at: days(-24),
    rating: 4,
    feedback: "Засыпали быстро, но асфальт положили не везде.",
  }),
  request({
    id: 120,
    category: "garbage",
    description: "Мусор у контейнерной площадки",
    status: "done",
    created_at: days(-28),
    rating: 5,
  }),
  request({
    id: 118,
    category: "meter_error",
    description: "Ошибка в показаниях за июль",
    status: "done",
    created_at: days(-33),
    rating: 4,
    has_photos: false,
  }),
  request({
    id: 112,
    category: "charge_dispute",
    description: "Спор по начислению за отопление",
    status: "done",
    created_at: days(-40),
    rating: 5,
    has_photos: false,
  }),
  request({
    id: 108,
    category: "other",
    description: "Не работает домофон у первого подъезда",
    status: "done",
    created_at: days(-46),
    rating: 5,
  }),
];
