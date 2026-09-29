import type { components } from "../../schema/generated";

import { fileUrl } from "./files";
import { addressOf, findHouse } from "./houses";
import { residencyForHouse } from "./profile";
import { days, minutes, shift } from "./time";

type Schemas = components["schemas"];

type MockRequest = {
  id: number;
  house_id: number;
  created_at: string;
  category: Schemas["RequestCategory"];
  description: string;
  status: Schemas["RequestStatus"];
  channel: Schemas["RequestChannel"];
  has_attachments: boolean;
  group_size: number;
  group_id: number | null;
  flat_number: string | null;
  executor_name: string | null;
  rating: number | null;
  feedback: string | null;
  has_result_attachments: boolean;
  deadline_at: string | null;
  escalated_at: string | null;
  parent_request_id: number | null;
  completion_reason: Schemas["RequestCompletionReason"] | null;
  attachment_names: string[];
  messages: {
    after_minutes: number;
    text: string;
    author_role?: string;
    author_name?: string;
    is_internal?: boolean;
  }[];
};

const request = (
  fields: Pick<
    MockRequest,
    "id" | "category" | "description" | "status" | "created_at"
  > &
    Partial<MockRequest>,
): MockRequest => {
  const item: MockRequest = {
    house_id: 1,
    channel: "miniapp",
    has_attachments: true,
    group_size: 1,
    group_id: null,
    flat_number: "45",
    executor_name: null,
    rating: null,
    feedback: null,
    has_result_attachments: false,
    deadline_at: null,
    escalated_at: null,
    parent_request_id: null,
    completion_reason: null,
    attachment_names: [],
    messages: [],
    ...fields,
  };

  if (item.status === "done" && item.completion_reason === null) {
    item.completion_reason = "resident_accepted";
  }

  return item;
};

const requests: MockRequest[] = [
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
      {
        after_minutes: 26 * 60,
        author_role: "executor",
        author_name: "Слесарь Ринат Хайруллин",
        text: "Водоканал заменил задвижку, стояк заполняем. К вечеру вода должна пойти.",
      },
    ],
  }),
  request({
    id: 142,
    category: "leak",
    description: "Протечка, 2-й подъезд",
    status: "in_progress",
    created_at: minutes(-150),
    deadline_at: minutes(90),
    group_size: 7,
    group_id: 12,
    executor_name: "Сантехник Алексей Петров",
    messages: [
      {
        after_minutes: 18,
        text: "Заявку приняли, передаём сантехнику. Напишем, когда назначим время.",
      },
      {
        after_minutes: 62,
        author_role: "executor",
        author_name: "Сантехник Алексей Петров",
        is_internal: true,
        text: "Не смогу приехать сегодня: на Баумана, 7 прорыв, работаю там до конца смены.",
      },
      {
        after_minutes: 104,
        text: "Сантехник уже выехал, будет в течение часа. Обеспечьте, пожалуйста, доступ в квартиру.",
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
    created_at: days(-2),
    deadline_at: days(-1),
    executor_name: "Механик Ильдар Гафуров",
    has_result_attachments: true,
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
    has_attachments: false,
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
    has_attachments: false,
  }),
  request({
    id: 112,
    category: "charge_dispute",
    description: "Спор по начислению за отопление",
    status: "done",
    created_at: days(-40),
    rating: 5,
    has_attachments: false,
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

const CATEGORY_RULES: Record<
  Schemas["RequestCategory"],
  {
    label: string;
    zone: Schemas["ResponsibilityZone"];
    hours: number;
    text: string;
    react?: string;
    basis?: string;
  }
> = {
  leak: {
    label: "Протечка",
    zone: "management",
    hours: 72,
    text: "3 суток",
    react: "30 минут",
    basis: "ПП РФ № 416, п. 13",
  },
  elevator: { label: "Лифт", zone: "management", hours: 24, text: "24 часа" },
  garbage: { label: "Мусор", zone: "management", hours: 24, text: "24 часа" },
  heating: {
    label: "Отопление",
    zone: "management",
    hours: 16,
    text: "16 часов",
    basis: "ПП РФ № 354, прил. 1, п. 14",
  },
  water_supply: {
    label: "Водоснабжение",
    zone: "utility",
    hours: 4,
    text: "4 часа",
    basis: "ПП РФ № 354, прил. 1, п. 1, 4",
  },
  electricity: {
    label: "Электричество",
    zone: "management",
    hours: 24,
    text: "24 часа",
    basis: "ПП РФ № 354, прил. 1, п. 9",
  },
  entrance: {
    label: "Подъезд",
    zone: "management",
    hours: 72,
    text: "3 суток",
  },
  yard: {
    label: "Двор и территория",
    zone: "management",
    hours: 72,
    text: "3 суток",
  },
  meter_error: {
    label: "Ошибка в показаниях",
    zone: "management",
    hours: 336,
    text: "10 рабочих дней",
    basis: "ПП РФ № 354, п. 31 «е(2)»",
  },
  charge_dispute: {
    label: "Спор по начислению",
    zone: "management",
    hours: 336,
    text: "10 рабочих дней",
    basis:
      "ПП РФ № 416, п. 36; проверка начисления - при обращении или по договоренности до 1 месяца, ПП РФ № 354, п. 31 «д»",
  },
  other: {
    label: "Другое",
    zone: "management",
    hours: 336,
    text: "10 рабочих дней",
    basis: "ПП РФ № 416, п. 36",
  },
};

let nextRequestId = 150;

export const houseRequests = (
  houseId: number,
  status: Schemas["RequestStatus"] | null,
): MockRequest[] =>
  requests
    .filter(
      (item) =>
        item.house_id === houseId &&
        (status === null || item.status === status),
    )
    .sort((a, b) => b.created_at.localeCompare(a.created_at));

export const requestListItem = (
  item: MockRequest,
): Schemas["RequestListItem"] => ({
  id: item.id,
  created_at: item.created_at,
  category: item.category,
  category_label: CATEGORY_RULES[item.category].label,
  description: item.description,
  status: item.status,
  channel: item.channel,
  has_photos: item.has_attachments,
  group_size: item.group_size,
  flat_number: item.flat_number,
  group_id: item.group_id,
  executor_name: item.executor_name,
  rating: item.rating,
  deadline_at: item.deadline_at,
  completion_reason: item.completion_reason,
  escalated_at: item.escalated_at,
});

const STEP: {
  status: Schemas["RequestStatus"];
  after_minutes: number;
  by_role: string;
}[] = [
  { status: "new", after_minutes: 0, by_role: "resident" },
  { status: "accepted", after_minutes: 17, by_role: "staff" },
  { status: "in_progress", after_minutes: 102, by_role: "staff" },
  { status: "on_review", after_minutes: 1320, by_role: "executor" },
  { status: "done", after_minutes: 1440, by_role: "resident" },
];

const requestTimeline = (
  item: MockRequest,
): Schemas["RequestStatusLogItem"][] => {
  const reached = STEP.findIndex(({ status }) => status === item.status);

  return STEP.slice(0, reached + 1).map((step, index) => ({
    at: shift(item.created_at, step.after_minutes),
    to_status: step.status,
    by_role:
      step.status === "done" && item.completion_reason === "auto_closed"
        ? "system"
        : step.by_role,
    from_status: index === 0 ? null : STEP[index - 1].status,
  }));
};

const RESULT_PHOTO: Schemas["FileRef"] = {
  is_video: false,
  name: "Фото исполнителя",
  url: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Crect width='120' height='120' fill='%23c7d4e0'/%3E%3C/svg%3E",
};

const PHOTO: Schemas["FileRef"] = {
  is_video: false,
  name: "Фото от жителя",
  url: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Crect width='120' height='120' fill='%23d9d9d9'/%3E%3C/svg%3E",
};

const requestAttachments = (item: MockRequest): Schemas["FileRef"][] => {
  if (item.attachment_names.length > 0) {
    return item.attachment_names.map((name) => ({
      name,
      is_video: /\.(mp4|mov)$/.test(name),
      url: fileUrl(name) || PHOTO.url,
    }));
  }

  return item.has_attachments ? [PHOTO] : [];
};

export const requestMessages = (
  item: MockRequest,
): Schemas["RequestMessageItem"][] =>
  item.messages.map((message) => ({
    created_at: shift(item.created_at, message.after_minutes),
    author_role: message.author_role ?? "staff",
    author_name: message.author_name ?? "Диспетчер УК",
    text: message.text,
    is_internal: message.is_internal ?? false,
  }));

export const requestCard = (item: MockRequest): Schemas["RequestCard"] => {
  const timeline = requestTimeline(item);
  const react = shift(item.created_at, 30);

  return {
    ...requestListItem(item),
    house_id: item.house_id,
    address: addressOf(item.house_id),
    org_name: findHouse(item.house_id)?.org?.name ?? null,
    deadline_text: CATEGORY_RULES[item.category].text,
    deadline_basis: CATEGORY_RULES[item.category].basis ?? null,
    react_deadline_at: !CATEGORY_RULES[item.category].react
      ? null
      : item.deadline_at && item.deadline_at < react
        ? item.deadline_at
        : react,
    photos: requestAttachments(item),
    result_photos: item.has_result_attachments ? [RESULT_PHOTO] : [],
    messages: requestMessages(item).filter((message) => !message.is_internal),
    timeline,
    can_review: item.status === "on_review",
    can_rate:
      item.completion_reason === "resident_accepted" && item.rating === null,
    feedback: item.feedback,
    parent_request_id: item.parent_request_id,
    flat_id: residencyForHouse(item.house_id)?.flat_id ?? null,
    auto_close_at:
      item.status === "on_review" ? shift(timeline[3].at, 48 * 60) : null,
    can_demo_expire: canDemoExpire(item),
    rejection_needs_photo: !["meter_error", "charge_dispute"].includes(
      item.category,
    ),
  };
};

export const findRequest = (requestId: number): MockRequest | undefined =>
  requests.find((item) => item.id === requestId);

const NEIGHBOURS: Partial<Record<Schemas["RequestCategory"], number>> = {
  heating: 3,
  elevator: 1,
};

export const similarRequests = (
  houseId: number,
  category: Schemas["RequestCategory"],
): Schemas["SimilarRequestsResponse"] => {
  const group = requests.find(
    (item) =>
      item.house_id === houseId &&
      item.category === category &&
      item.group_id !== null &&
      item.status !== "done",
  );

  if (group) {
    return {
      category,
      neighbours_count: group.group_size,
      can_join: true,
      group_id: group.group_id,
      window_started_at: group.created_at,
    };
  }

  return {
    category,
    neighbours_count: NEIGHBOURS[category] ?? 0,
    can_join: false,
    group_id: null,
    window_started_at: null,
  };
};

export const createRequest = (
  houseId: number,
  body: Schemas["CreateRequestRequest"],
): MockRequest => {
  const created = request({
    id: nextRequestId++,
    house_id: houseId,
    category: body.category,
    description: body.description,
    status: "new",
    created_at: minutes(0),
    deadline_at: categoryDeadline(body.category),
    flat_number: residencyForHouse(houseId)?.flat_number ?? null,
    group_id: body.join_group_id ?? null,
    has_attachments: (body.photos?.length ?? 0) > 0,
    attachment_names: body.photos ?? [],
  });
  requests.push(created);

  if (created.group_id !== null) {
    const members = requests.filter(
      (item) => item.group_id === created.group_id && item.id !== created.id,
    );
    const size = (members[0]?.group_size ?? 0) + 1;

    [...members, created].forEach((item) => {
      item.group_size = size;
    });
  }

  return created;
};

export const repeatRequest = (
  item: MockRequest,
  description: string | null,
  attachments: string[],
): MockRequest => {
  const created = request({
    id: nextRequestId++,
    house_id: item.house_id,
    category: item.category,
    description: description?.trim() || `Повторно по заявке №${item.id}`,
    status: "new",
    created_at: minutes(0),
    deadline_at: categoryDeadline(item.category),
    flat_number: item.flat_number,
    parent_request_id: item.id,
    has_attachments: attachments.length > 0,
    attachment_names: attachments,
  });
  requests.push(created);

  return created;
};

export const requestCategories = (): Schemas["RequestCategoryItem"][] =>
  Object.entries(CATEGORY_RULES).map(([category, rule]) => ({
    category: category as Schemas["RequestCategory"],
    label: rule.label,
    zone: rule.zone,
    deadline_text: rule.text,
    react_text: rule.react ?? null,
    deadline_basis: rule.basis ?? null,
  }));

export const categoryDeadline = (category: Schemas["RequestCategory"]) =>
  minutes(CATEGORY_RULES[category].hours * 60);

export const canDemoExpire = (item: MockRequest) =>
  Boolean(findHouse(item.house_id)?.org?.is_demo) &&
  ["new", "accepted", "in_progress"].includes(item.status) &&
  item.deadline_at !== null &&
  new Date(item.deadline_at).getTime() > Date.now();
