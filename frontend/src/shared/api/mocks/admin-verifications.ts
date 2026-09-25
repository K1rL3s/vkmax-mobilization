import type { components } from "../schema/generated";

import {
  badRequest,
  conflict,
  endpoint,
  notFound,
  number,
  ok,
  page,
  type Reply,
} from "./reply";
import {
  addressOf,
  days,
  findFlat,
  latestVerification,
  residencies,
  setVerified,
  verificationRequestItem,
} from "./state";

type Schemas = components["schemas"];

type Item = Schemas["VerificationRequestItem"];

const MOVED_OUT_ID = 8106;

const seed = (
  fields: Pick<
    Item,
    | "id"
    | "created_at"
    | "house_id"
    | "flat_number"
    | "user_name"
    | "account_no"
  > &
    Partial<Item>,
): Item => ({
  flat_id: fields.id + 1000,
  user_id: fields.id + 2000,
  address:
    fields.house_id === 3
      ? "Республика Татарстан, Казань, ул. Академика Арбузова, д. 16, корпус 2"
      : addressOf(fields.house_id),
  status: "pending",
  comment: null,
  reason: null,
  ...fields,
});

const seeded: Item[] = [
  seed({
    id: 8101,
    created_at: days(-9),
    house_id: 1,
    flat_number: "12",
    user_name: "Гульнара Ахметзяновна Сафиуллина-Валиева",
    account_no: "1600120088",
    comment:
      "Квитанции приходят на девичью фамилию, в паспорте она другая. Лицевой счёт переписан с последней квитанции за август, но в личном кабинете расчётного центра у него другой номер - там на две цифры длиннее. Подскажите, какой из них правильный, я перезаявлю.",
  }),
  seed({
    id: 8102,
    created_at: days(-7),
    house_id: 2,
    flat_number: "3",
    user_name: "Пётр Сергеев",
    account_no: "1400030077",
    comment: "Купил квартиру в июле, квитанции ещё на прежнего собственника.",
  }),
  seed({
    id: 8103,
    created_at: days(-5),
    house_id: 3,
    flat_number: "118",
    user_name: "Алла Гринёва",
    account_no: "1601180204",
    comment: null,
  }),
  seed({
    id: 8104,
    created_at: days(-4),
    house_id: 1,
    flat_number: "7",
    user_name: "Игорь Тимофеев",
    account_no: "16-00-07-0055",
    comment: "Счёт с квитанции, набрал с дефисами, как напечатано.",
  }),
  seed({
    id: 8105,
    created_at: days(-3),
    house_id: 3,
    flat_number: "204",
    user_name: "Марина Козлова",
    account_no: "1602040311",
    comment: "Живу по договору найма, квитанции забирает собственник.",
  }),
  seed({
    id: MOVED_OUT_ID,
    created_at: days(-2),
    house_id: 2,
    flat_number: "56",
    user_name: "Денис Лапшин",
    account_no: "1400560142",
    comment: "Переехал внутри дома, старую квартиру сдал.",
  }),
  seed({
    id: 8107,
    created_at: days(-1),
    house_id: 1,
    flat_number: "90",
    user_name: "Ольга Белова",
    account_no: "1600900027",
    comment: null,
  }),
  seed({
    id: 8108,
    created_at: days(-1),
    house_id: 3,
    flat_number: "33",
    user_name: "Рустем Хайруллин",
    account_no: "1600330176",
    comment: "Счётчики хочу подавать сам, а не через соседа.",
  }),
  seed({
    id: 8109,
    created_at: days(-6),
    house_id: 1,
    flat_number: "45",
    user_name: "Анна Морозова",
    account_no: "1600450012",
    status: "approved",
    comment: "Квитанция за сентябрь на руках.",
  }),
  seed({
    id: 8110,
    created_at: days(-8),
    house_id: 2,
    flat_number: "11",
    user_name: "Виктор Панов",
    account_no: "0000000000",
    status: "rejected",
    comment: "Номер списал с домофонной карточки.",
    reason: "Лицевой счёт не совпал с данными УК",
  }),
];

const live = () =>
  residencies().flatMap((residency) => {
    const flat =
      residency.flat_id === null ? null : findFlat(residency.flat_id);
    const request = flat ? latestVerification(flat.id) : undefined;

    return flat && request ? [{ residency, flat, request }] : [];
  });

const decide = (
  id: number,
  status: "approved" | "rejected",
  reason: string | null,
): Reply => {
  const item = seeded.find((candidate) => candidate.id === id);
  const found = item
    ? undefined
    : live().find(({ request }) => request.id === id);
  const target = item ?? found?.request;

  if (!target) {
    return notFound("Запрос подтверждения не найден");
  }

  if (target.status !== "pending") {
    return conflict("Запрос подтверждения уже рассмотрен");
  }

  if (status === "approved" && id === MOVED_OUT_ID) {
    return conflict("Житель привязан к другой квартире, переезд оформляет УК");
  }

  target.status = status;

  if (reason !== null) {
    target.reason = reason;
  }

  if (found && status === "approved") {
    setVerified(found.residency, found.flat.id);
  }

  return ok(item ?? verificationRequestItem(found!.request, found!.flat));
};

export const adminVerificationsConfigs = [
  endpoint("get", "/admin/verification-requests", (request) => {
    const status = request.query.status;
    const houseId = number(request.query.house_id);

    return ok(
      page(
        [
          ...live().map(({ request, flat }) =>
            verificationRequestItem(request, flat),
          ),
          ...seeded,
        ]
          .sort((a, b) => b.created_at.localeCompare(a.created_at))
          .filter(
            (item) =>
              (status === undefined || item.status === status) &&
              (houseId === null || item.house_id === houseId),
          ),
        request.query,
      ) satisfies Schemas["Page_VerificationRequestItem_"],
    );
  }),
  endpoint(
    "post",
    "/admin/verification-requests/:verification_id/approve",
    (request) =>
      decide(Number(request.params.verification_id), "approved", null),
  ),
  endpoint(
    "post",
    "/admin/verification-requests/:verification_id/reject",
    (request) => {
      const reason =
        typeof request.body.reason === "string"
          ? request.body.reason.trim()
          : "";

      return reason
        ? decide(Number(request.params.verification_id), "rejected", reason)
        : badRequest("Укажите причину отказа");
    },
  ),
];
