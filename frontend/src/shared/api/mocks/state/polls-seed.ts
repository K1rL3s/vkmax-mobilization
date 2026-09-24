import { days } from "./time";

export type MockPollVote = {
  // голос самого жителя: из него берутся my_option_ids и запрет второго голоса
  is_mine: boolean;
  flat_id: number | null;
  option_ids: number[];
  // голос без веса: житель не подтвердил квартиру либо за эту квартиру уже
  // проголосовал другой собственник
  counted_by_area: boolean;
};

export type MockPoll = {
  id: number;
  house_id: number;
  title: string;
  description: string | null;
  created_by_role: string;
  // опрос завёл сам житель: на бэке это created_by_user_id, наружу уходит
  // одним признаком can_manage
  created_by_me: boolean;
  is_multiple: boolean;
  closed: boolean;
  created_at: string;
  ends_at: string;
  options: { id: number; text: string }[];
  votes: MockPollVote[];
};

// шесть состояний блока разом: идущий без моего голоса и с ним, закрытый с
// кворумом и без, опрос с мнениями без веса и мультивыборный. Площади квартир
// дома неровные, две квартиры без площади - процент считается не на удобных
// числах
export const SEED_POLLS: MockPoll[] = [
  {
    id: 301,
    house_id: 1,
    title: "Ремонт подъезда: что делать в первую очередь",
    description:
      "УК выделила смету на один вид работ в этом году. Выберите, с чего начать.",
    created_by_role: "chairman",
    created_by_me: false,
    is_multiple: false,
    closed: false,
    created_at: days(-2),
    ends_at: days(2),
    options: [
      { id: 511, text: "Покрасить стены" },
      { id: 512, text: "Заменить окна" },
      { id: 513, text: "Починить почтовые ящики" },
    ],
    votes: [
      { is_mine: true, flat_id: 101, option_ids: [512], counted_by_area: true },
      {
        is_mine: false,
        flat_id: 102,
        option_ids: [511],
        counted_by_area: true,
      },
      {
        is_mine: false,
        flat_id: 103,
        option_ids: [512],
        counted_by_area: true,
      },
      {
        is_mine: false,
        flat_id: 109,
        option_ids: [512],
        counted_by_area: true,
      },
      {
        is_mine: false,
        flat_id: 111,
        option_ids: [511],
        counted_by_area: true,
      },
    ],
  },
  {
    id: 302,
    house_id: 1,
    title: "Установка шлагбаума во дворе",
    description:
      "Двор открыт для сквозного проезда, мест для жителей не хватает.",
    created_by_role: "chairman",
    created_by_me: true,
    is_multiple: false,
    closed: false,
    created_at: days(-4),
    ends_at: days(5),
    options: [
      { id: 521, text: "За" },
      { id: 522, text: "Против" },
      { id: 523, text: "Воздержусь" },
    ],
    votes: [
      {
        is_mine: false,
        flat_id: 102,
        option_ids: [521],
        counted_by_area: true,
      },
      {
        is_mine: false,
        flat_id: 107,
        option_ids: [521],
        counted_by_area: true,
      },
      {
        is_mine: false,
        flat_id: 110,
        option_ids: [521],
        counted_by_area: true,
      },
    ],
  },
  {
    id: 303,
    house_id: 1,
    title: "Где поставить детскую площадку",
    description: null,
    created_by_role: "chairman",
    created_by_me: false,
    is_multiple: false,
    closed: false,
    created_at: days(-6),
    ends_at: days(9),
    options: [
      { id: 531, text: "У первого подъезда" },
      { id: 532, text: "За домом, у сквера" },
    ],
    votes: [
      {
        is_mine: false,
        flat_id: 102,
        option_ids: [531],
        counted_by_area: true,
      },
      {
        is_mine: false,
        flat_id: 107,
        option_ids: [532],
        counted_by_area: true,
      },
      {
        is_mine: false,
        flat_id: 106,
        option_ids: [531],
        counted_by_area: false,
      },
      {
        is_mine: false,
        flat_id: 108,
        option_ids: [532],
        counted_by_area: false,
      },
      {
        is_mine: false,
        flat_id: null,
        option_ids: [531],
        counted_by_area: false,
      },
    ],
  },
  {
    id: 304,
    house_id: 1,
    title: "Что благоустроить во дворе в этом году",
    description: "Можно выбрать несколько вариантов.",
    created_by_role: "chairman",
    created_by_me: false,
    is_multiple: true,
    closed: false,
    created_at: days(-8),
    ends_at: days(14),
    options: [
      { id: 541, text: "Детская площадка" },
      { id: 542, text: "Парковка" },
      { id: 543, text: "Озеленение" },
      { id: 544, text: "Освещение" },
    ],
    votes: [
      {
        is_mine: false,
        flat_id: 102,
        option_ids: [541, 543],
        counted_by_area: true,
      },
      {
        is_mine: false,
        flat_id: 103,
        option_ids: [543],
        counted_by_area: true,
      },
      {
        is_mine: false,
        flat_id: 109,
        option_ids: [542],
        counted_by_area: true,
      },
      {
        is_mine: false,
        flat_id: 110,
        option_ids: [541, 544],
        counted_by_area: true,
      },
    ],
  },
  {
    id: 305,
    house_id: 1,
    title: "Переход на прямые договоры с ресурсоснабжающими организациями",
    description: null,
    created_by_role: "staff",
    created_by_me: false,
    is_multiple: false,
    closed: true,
    created_at: days(-20),
    ends_at: days(-3),
    options: [
      { id: 551, text: "Поддерживаю" },
      { id: 552, text: "Не поддерживаю" },
    ],
    votes: [
      { is_mine: true, flat_id: 101, option_ids: [552], counted_by_area: true },
      {
        is_mine: false,
        flat_id: 102,
        option_ids: [551],
        counted_by_area: true,
      },
      {
        is_mine: false,
        flat_id: 103,
        option_ids: [551],
        counted_by_area: true,
      },
      {
        is_mine: false,
        flat_id: 107,
        option_ids: [551],
        counted_by_area: true,
      },
      {
        is_mine: false,
        flat_id: 109,
        option_ids: [551],
        counted_by_area: true,
      },
      {
        is_mine: false,
        flat_id: 110,
        option_ids: [552],
        counted_by_area: true,
      },
      {
        is_mine: false,
        flat_id: 111,
        option_ids: [551],
        counted_by_area: true,
      },
    ],
  },
  {
    id: 306,
    house_id: 1,
    title: "Смена подрядчика по уборке двора",
    description: null,
    created_by_role: "chairman",
    created_by_me: true,
    is_multiple: false,
    closed: true,
    created_at: days(-30),
    ends_at: days(-10),
    options: [
      { id: 561, text: "Сменить" },
      { id: 562, text: "Оставить текущего" },
    ],
    votes: [
      {
        is_mine: false,
        flat_id: 103,
        option_ids: [561],
        counted_by_area: true,
      },
      {
        is_mine: false,
        flat_id: 110,
        option_ids: [562],
        counted_by_area: true,
      },
    ],
  },
];

// голоса живут внутри опроса и правятся голосованием, поэтому сид копируется
// вглубь: иначе первый же голос осел бы в константе и пережил сброс состояния
export const seedPolls = (): MockPoll[] =>
  SEED_POLLS.map((poll) => ({ ...poll, votes: [...poll.votes] }));
