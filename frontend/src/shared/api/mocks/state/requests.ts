import type { components } from "../../schema/generated";

type Schemas = components["schemas"];

import { fileUrl } from "./files";
import { address, findHouse } from "./houses";
import { residencyForHouse } from "./profile";
import { SEED_REQUESTS, request, type MockRequest } from "./requests-seed";
import { minutes, shift } from "./time";

// копия CATEGORY_RULES бэка: справочник категорий отдаёт те же подписи,
// зоны и нормативы
const CATEGORY_RULES: Record<
  Schemas["RequestCategory"],
  { label: string; zone: Schemas["ResponsibilityZone"]; hours: number }
> = {
  leak: { label: "Протечка", zone: "management", hours: 4 },
  elevator: { label: "Лифт", zone: "management", hours: 24 },
  garbage: { label: "Мусор", zone: "management", hours: 24 },
  heating: { label: "Отопление", zone: "utility", hours: 24 },
  water_supply: { label: "Водоснабжение", zone: "utility", hours: 8 },
  electricity: { label: "Электричество", zone: "utility", hours: 24 },
  entrance: { label: "Подъезд", zone: "management", hours: 72 },
  yard: { label: "Двор и территория", zone: "municipality", hours: 72 },
  meter_error: { label: "Ошибка в показаниях", zone: "management", hours: 72 },
  charge_dispute: {
    label: "Спор по начислению",
    zone: "management",
    hours: 72,
  },
  other: { label: "Другое", zone: "management", hours: 72 },
};

const state = {
  requests: [...SEED_REQUESTS],
  nextRequestId: 150,
};

export const resetRequests = (): void => {
  state.requests = [...SEED_REQUESTS];
  state.nextRequestId = 150;
};

export const houseRequests = (
  houseId: number,
  status: Schemas["RequestStatus"] | null,
): MockRequest[] =>
  state.requests
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
  has_photos: item.has_photos,
  group_size: item.group_size,
  flat_number: item.flat_number,
  group_id: item.group_id,
  executor_name: item.executor_name,
  rating: item.rating,
  deadline_at: item.deadline_at,
  completion_reason: item.completion_reason,
});

// заявка держит только случившееся; шаг помечается ролью того, кто его сделал
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

// бэковая AUTO_CLOSE_AFTER: момент автозакрытия считает бэк, мок стоит на
// его месте и считает так же - от шага «На приёмке»
const autoCloseAt = (item: MockRequest): string | null => {
  if (item.status !== "on_review") {
    return null;
  }

  const sent = requestTimeline(item).find(
    (entry) => entry.to_status === "on_review",
  );

  return sent ? shift(sent.at, 48 * 60) : null;
};

const RESULT_PHOTO: Schemas["FileRef"] = {
  name: "Фото исполнителя",
  url: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Crect width='120' height='120' fill='%23c7d4e0'/%3E%3C/svg%3E",
};

const PHOTO: Schemas["FileRef"] = {
  name: "Фото от жителя",
  url: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Crect width='120' height='120' fill='%23d9d9d9'/%3E%3C/svg%3E",
};

// загруженные фото приезжают по именам, демо-заявки обходятся заглушкой
const requestPhotos = (item: MockRequest): Schemas["FileRef"][] => {
  if (item.photo_names.length > 0) {
    return item.photo_names.map((name) => ({
      name,
      url: fileUrl(name) || PHOTO.url,
    }));
  }

  return item.has_photos ? [PHOTO] : [];
};

export const requestCard = (item: MockRequest): Schemas["RequestCard"] => {
  const house = findHouse(item.house_id);

  return {
    ...requestListItem(item),
    house_id: item.house_id,
    address: house ? address(house) : "",
    org_name: house?.org?.name ?? null,
    normative_hours: CATEGORY_RULES[item.category].hours,
    photos: requestPhotos(item),
    result_photos: item.has_result_photos ? [RESULT_PHOTO] : [],
    messages: item.messages.map((message) => ({
      created_at: shift(item.created_at, message.after_minutes),
      author_role: "staff",
      author_name: "Диспетчер УК",
      text: message.text,
    })),
    timeline: requestTimeline(item),
    can_review: item.status === "on_review",
    can_rate:
      item.completion_reason === "resident_accepted" && item.rating === null,
    feedback: item.feedback,
    parent_request_id: item.parent_request_id,
    flat_id: residencyForHouse(item.house_id)?.flat_id ?? null,
    auto_close_at: autoCloseAt(item),
  };
};

export const findRequest = (requestId: number): MockRequest | undefined =>
  state.requests.find((item) => item.id === requestId);

// приёмка закрывает заявку в обе стороны; отказ отличается причиной, по
// которой заявку потом нельзя оценить
export const acceptRequest = (item: MockRequest): MockRequest => {
  item.status = "done";
  item.completion_reason = "resident_accepted";

  return item;
};

export const rejectRequest = (item: MockRequest): MockRequest => {
  item.status = "done";
  item.completion_reason = "resident_rejected";

  return item;
};

export const rateRequest = (
  item: MockRequest,
  rating: number,
  feedback: string | null,
): MockRequest => {
  item.rating = rating;
  item.feedback = feedback;

  return item;
};

// демо-соседи: у протечки уже собрана группа, к отоплению присоединиться
// нельзя - окно склейки закрыто, но пожаловавшиеся соседи есть
const NEIGHBOURS: Partial<Record<Schemas["RequestCategory"], number>> = {
  heating: 3,
  elevator: 1,
};

export const similarRequests = (
  houseId: number,
  category: Schemas["RequestCategory"],
): Schemas["SimilarRequestsResponse"] => {
  const group = state.requests.find(
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
    id: state.nextRequestId,
    house_id: houseId,
    category: body.category,
    description: body.description,
    status: "new",
    created_at: minutes(0),
    deadline_at: minutes(CATEGORY_RULES[body.category].hours * 60),
    flat_number: residencyForHouse(houseId)?.flat_number ?? null,
    group_id: body.join_group_id ?? null,
    has_photos: (body.photos?.length ?? 0) > 0,
    photo_names: body.photos ?? [],
  });
  state.nextRequestId += 1;
  state.requests.push(created);

  // присоединение растит группу: новое число квартир видят все её заявки
  if (created.group_id !== null) {
    const members = state.requests.filter(
      (item) => item.group_id === created.group_id && item.id !== created.id,
    );
    const size = (members[0]?.group_size ?? 0) + 1;

    [...members, created].forEach((item) => {
      item.group_size = size;
    });
  }

  return created;
};

// повтор наследует категорию и квартиру исходной заявки: житель жалуется на
// ту же проблему, а не заводит новую
export const repeatRequest = (
  item: MockRequest,
  description: string | null,
  photos: string[],
): MockRequest => {
  const created = request({
    id: state.nextRequestId,
    house_id: item.house_id,
    category: item.category,
    description: description?.trim() || `Повторно по заявке №${item.id}`,
    status: "new",
    created_at: minutes(0),
    deadline_at: minutes(CATEGORY_RULES[item.category].hours * 60),
    flat_number: item.flat_number,
    parent_request_id: item.id,
    has_photos: photos.length > 0,
    photo_names: photos,
  });
  state.nextRequestId += 1;
  state.requests.push(created);

  return created;
};

export const requestCategories = (): Schemas["RequestCategoryItem"][] =>
  Object.entries(CATEGORY_RULES).map(([category, rule]) => ({
    category: category as Schemas["RequestCategory"],
    label: rule.label,
    zone: rule.zone,
    normative_hours: rule.hours,
  }));
