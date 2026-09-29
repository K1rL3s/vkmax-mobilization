import type { components } from "../schema/generated";

import { houseResidents } from "./admin-houses";
import {
  badRequest,
  conflict,
  endpoint,
  notFound,
  number,
  ok,
  page,
} from "./reply";
import {
  addressOf,
  categoryDeadline,
  findFlat,
  findHouse,
  houseRequests,
  requestCard,
  requestMessages,
  requestCategories,
  user,
} from "./state";

type Schemas = components["schemas"];
type Request = Schemas["AdminRequestCard"];

const houseIds = [1, 2, 3];
const statusOrder: Schemas["RequestStatus"][] = [
  "new",
  "accepted",
  "in_progress",
  "on_review",
  "done",
];
const executors: Schemas["ExecutorItem"][] = [
  {
    user_id: 31,
    name: "Алексей Петров",
    username: "petrov",
    active_requests: 0,
  },
  {
    user_id: 32,
    name: "Мария Александровна Иванова-Воскресенская",
    username: "ivanova",
    active_requests: 0,
  },
];

const fromResident = (
  item: ReturnType<typeof houseRequests>[number],
): Request => ({
  ...structuredClone(requestCard(item)),
  messages: requestMessages(item),
  is_staff_author: false,
  author_name: "Гульнара Ахметзяновна Сафиуллина-Валиева",
  caller_name: null,
  caller_phone: null,
  executor_user_id: item.executor_name ? 31 : null,
  executor_name: item.executor_name ? executors[0].name : null,
});

const requests: Request[] = houseIds.flatMap((houseId) =>
  houseRequests(houseId, null).map(fromResident),
);

const includeResidentRequests = () => {
  for (const houseId of houseIds) {
    for (const item of houseRequests(houseId, null)) {
      if (!requests.some((request) => request.id === item.id)) {
        requests.push(fromResident(item));
      }
    }
  }
};

let nextId = Math.max(1000, ...requests.map((request) => request.id)) + 1;

const makeRequest = (houseId: number, fields: Partial<Request>): Request => {
  const category = requestCategories().find(
    (item) => item.category === (fields.category ?? "other"),
  )!;
  const at = new Date().toISOString();
  return {
    id: nextId++,
    house_id: houseId,
    address: addressOf(houseId),
    org_name: findHouse(houseId)!.org?.name ?? null,
    created_at: at,
    category: category.category,
    category_label: category.label,
    description:
      "Не работает освещение на лестничной площадке. Просим прислать мастера.",
    status: "new",
    channel: "phone",
    is_staff_author: true,
    author_name: null,
    caller_name: null,
    caller_phone: null,
    has_photos: false,
    photos: [],
    result_photos: [],
    group_id: null,
    group_size: 1,
    flat_id: null,
    flat_number: null,
    executor_user_id: null,
    executor_name: null,
    rating: null,
    feedback: null,
    completion_reason: null,
    deadline_text: category.deadline_text,
    deadline_basis: category.deadline_basis,
    pp290_refs: category.pp290_refs,
    react_deadline_at: null,
    deadline_at: categoryDeadline(category.category),
    messages: [],
    timeline: [{ at, to_status: "new", by_role: "staff" }],
    can_review: false,
    can_rate: false,
    parent_request_id: null,
    auto_close_at: null,
    can_demo_expire: false,
    can_demo_neighbours: false,
    ...fields,
  };
};

for (const groupId of new Set(
  requests.flatMap((request) =>
    request.group_id == null ? [] : [request.group_id],
  ),
)) {
  const members = requests.filter((request) => request.group_id === groupId);
  const first = members[0];
  const count = Math.max(...members.map((request) => request.group_size));
  for (let index = members.length; index < count; index++) {
    requests.push(
      makeRequest(first.house_id, {
        category: first.category,
        category_label: first.category_label,
        description: first.description,
        deadline_text: first.deadline_text,
        deadline_basis: first.deadline_basis,
        pp290_refs: first.pp290_refs,
        deadline_at: first.deadline_at,
        group_id: groupId,
        group_size: count,
        status: first.status,
        timeline: structuredClone(first.timeline),
        channel: "bot",
        is_staff_author: false,
        author_name: `Автор из квартиры ${index + 20}`,
        flat_number: String(index + 20),
      }),
    );
  }
}
for (let index = 0; index < 3; index++) {
  requests.push(
    makeRequest(1, {
      category: "garbage",
      group_id: 21,
      group_size: 3,
      channel: "bot",
      is_staff_author: false,
      author_name: `Автор из квартиры ${index + 30}`,
      flat_number: String(index + 30),
      description:
        "Мусоропровод забит на четвёртом этаже, мусор стоит на площадке.",
      timeline: [
        { at: new Date().toISOString(), to_status: "new", by_role: "resident" },
      ],
    }),
  );
}
requests.push(
  makeRequest(2, {
    category: "electricity",
    category_label: "Электричество",
    caller_name: "Александр",
    caller_phone: "+7 999 123-45-67",
  }),
);
const repeatParent = requests.find((request) => request.status === "done")!;
requests.push(
  makeRequest(repeatParent.house_id, {
    parent_request_id: repeatParent.id,
    category: repeatParent.category,
    category_label: repeatParent.category_label,
    author_name: "Анна Морозова",
    channel: "miniapp",
    is_staff_author: false,
    description:
      "После ремонта проблема появилась снова. Проверьте соединение ещё раз.",
  }),
);

const findRequest = (id: string) => {
  includeResidentRequests();
  return requests.find((request) => request.id === Number(id));
};
const membersOf = (id: number) =>
  requests.filter((request) => request.group_id === id);
const closedGroups = new Set<number>();
const flatCount = (members: Request[]) =>
  new Set(
    members.flatMap((request) =>
      request.flat_number == null ? [] : [request.flat_number],
    ),
  ).size;
const listItem = (request: Request): Schemas["AdminRequestListItem"] => ({
  ...request,
  group_size:
    request.group_id == null ? 1 : flatCount(membersOf(request.group_id)),
});
const groupCard = (id: number): Schemas["RequestGroupCard"] | null => {
  const members = membersOf(id);
  const first = members[0];
  if (!first) return null;
  return {
    id,
    house_id: first.house_id,
    address: first.address,
    category: first.category,
    category_label: first.category_label,
    status: closedGroups.has(id) ? "closed" : "open",
    window_started_at: first.created_at,
    flats_count: flatCount(members),
    requests: members.map(listItem),
  };
};
const changeStatus = (
  request: Request,
  status: Schemas["RequestStatus"],
  comment?: string | null,
) => {
  const at = new Date().toISOString();
  request.timeline.push({
    at,
    from_status: request.status,
    to_status: status,
    by_role: "staff",
  });
  request.status = status;
  request.can_review = status === "on_review" && request.author_name != null;
  request.auto_close_at =
    status === "on_review"
      ? new Date(Date.now() + 48 * 3600000).toISOString()
      : null;
  if (comment?.trim())
    request.messages.push({
      created_at: at,
      author_role: "staff",
      author_name: user.name,
      text: comment.trim(),
      is_internal: false,
    });
};

export const adminRequestsConfigs = [
  endpoint("get", "/admin/requests", (request) => {
    includeResidentRequests();
    const found = requests
      .filter(
        (item) =>
          (!request.query.house_id ||
            item.house_id === number(request.query.house_id)) &&
          (!request.query.category ||
            item.category === request.query.category) &&
          (!request.query.status || item.status === request.query.status) &&
          (!request.query.channel || item.channel === request.query.channel) &&
          (!request.query.executor_user_id ||
            item.executor_user_id === number(request.query.executor_user_id)) &&
          (request.query.overdue !== "true" ||
            (item.status !== "done" &&
              item.status !== "on_review" &&
              !!item.deadline_at &&
              Date.parse(item.deadline_at) < Date.now())),
      )
      .sort((a, b) => b.created_at.localeCompare(a.created_at) || b.id - a.id);
    const rows =
      request.query.grouped === "true"
        ? found.filter(
            (item, index) =>
              item.group_id == null ||
              found.findIndex((other) => other.group_id === item.group_id) ===
                index,
          )
        : found;
    return ok(
      page(
        rows.map(listItem),
        request.query,
        50,
      ) satisfies Schemas["Page_AdminRequestListItem_"],
    );
  }),
  endpoint("get", "/admin/requests/:request_id", (request) => {
    const item = findRequest(request.params.request_id);
    return item
      ? ok({
          ...item,
          group_size: listItem(item).group_size,
        } satisfies Request)
      : notFound("Заявка не найдена");
  }),
  endpoint("post", "/admin/requests/:request_id/status", (request) => {
    const item = findRequest(request.params.request_id);
    if (!item) return notFound("Заявка не найдена");
    const body = request.body as Schemas["ChangeRequestStatusRequest"];
    if (!statusOrder.includes(body.status))
      return badRequest("Неизвестный статус");
    if (
      statusOrder.indexOf(body.status) !==
      statusOrder.indexOf(item.status) + 1
    )
      return conflict("Статус заявки меняется на следующий шаг");
    if (body.status === "done" && item.author_name != null)
      return conflict("Заявку закрывает житель после приёмки");
    changeStatus(item, body.status, body.comment);
    return ok(item);
  }),
  endpoint("post", "/admin/requests/:request_id/reply", (request) => {
    const item = findRequest(request.params.request_id);
    if (!item) return notFound("Заявка не найдена");
    const text =
      typeof request.body.text === "string" ? request.body.text.trim() : "";
    if (!text) return badRequest("Напишите ответ");
    item.messages.push({
      created_at: new Date().toISOString(),
      author_role: "staff",
      author_name: user.name,
      text,
      is_internal: false,
    });
    if (request.body.question === true && item.author_name != null)
      item.question_asked_at = new Date().toISOString();
    item.resident_answered_at = null;
    return ok(item);
  }),
  endpoint("post", "/admin/requests/:request_id/assign", (request) => {
    const item = findRequest(request.params.request_id);
    if (!item) return notFound("Заявка не найдена");
    const executor = executors.find(
      (person) => person.user_id === Number(request.body.user_id),
    );
    if (!executor) return badRequest("Выберите исполнителя");
    item.executor_user_id = executor.user_id;
    item.executor_name = executor.name;
    return ok(item);
  }),
  endpoint("get", "/admin/request-groups/:group_id", (request) => {
    const group = groupCard(Number(request.params.group_id));
    return group ? ok(group) : notFound("Коллективная заявка не найдена");
  }),
  endpoint("post", "/admin/request-groups/:group_id/status", (request) => {
    const id = Number(request.params.group_id);
    const members = membersOf(id);
    if (!members.length) return notFound("Коллективная заявка не найдена");
    const body = request.body as Schemas["ChangeGroupStatusRequest"];
    if (!statusOrder.includes(body.status))
      return badRequest("Неизвестный статус");
    const targetIndex = statusOrder.indexOf(body.status);
    if (
      members.every(
        (member) => statusOrder.indexOf(member.status) >= targetIndex,
      )
    )
      return conflict("Все заявки группы уже в этом статусе или дальше");
    if (
      body.status === "done" &&
      members.some(
        (member) => member.status !== "done" && member.author_name != null,
      )
    )
      return conflict("Заявки закрывают жители после приёмки");
    for (const member of members) {
      for (const step of statusOrder.slice(
        statusOrder.indexOf(member.status) + 1,
        targetIndex + 1,
      ))
        changeStatus(member, step, step === body.status ? body.comment : null);
    }
    if (body.status === "done") closedGroups.add(id);
    return ok(groupCard(id));
  }),
  endpoint("post", "/admin/requests/phone", (request) => {
    const body = request.body as Schemas["CreatePhoneRequestRequest"];
    if (!houseIds.includes(body.house_id)) return notFound("Дом не найден");
    if (
      !body.description?.trim() ||
      !requestCategories().some(
        (category) => category.category === body.category,
      )
    )
      return badRequest("Выберите категорию и опишите проблему");
    const resident = houseResidents(body.house_id).find(
      (person) => person.resident_id === body.resident_id,
    );
    if (body.resident_id && !resident)
      return notFound("Житель этого дома не найден");
    if (resident?.status === "blocked")
      return conflict("Житель заблокирован в доме");
    if (resident && body.flat_id && body.flat_id !== resident.flat_id)
      return badRequest("Квартира не принадлежит выбранному жителю");
    const flatId = resident ? resident.flat_id : body.flat_id;
    const flat = flatId ? findFlat(flatId) : null;
    if (flatId && (!flat || flat.house_id !== body.house_id))
      return notFound("Квартира этого дома не найдена");
    if (
      !resident &&
      !flat &&
      !(body.caller_name?.trim() && body.caller_phone?.trim())
    )
      return badRequest(
        "Выберите квартиру или укажите имя и телефон звонившего",
      );
    const item = makeRequest(body.house_id, {
      category: body.category,
      description: body.description.trim(),
      flat_id: flat?.id ?? null,
      flat_number: flat?.number ?? resident?.flat_number ?? null,
      author_name: resident?.name ?? null,
      is_staff_author: !resident,
      caller_name: body.caller_name?.trim() || null,
      caller_phone: body.caller_phone?.trim() || null,
    });
    requests.push(item);
    return ok(item);
  }),
  endpoint("get", "/admin/executors", () =>
    ok(
      executors.map((executor) => ({
        ...executor,
        active_requests: requests.filter(
          (request) =>
            request.executor_user_id === executor.user_id &&
            request.status !== "done",
        ).length,
      })),
    ),
  ),
];
