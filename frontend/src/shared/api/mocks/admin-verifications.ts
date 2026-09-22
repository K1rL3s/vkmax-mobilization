import type { components } from "../schema/generated";

import { badRequest, conflict, notFound, number, ok, route } from "./reply";
import {
  address,
  findFlat,
  findHouse,
  latestVerification,
  residencies,
  setVerified,
  verificationRequestItem,
} from "./state";

type Schemas = components["schemas"];

type Item = Schemas["VerificationRequestItem"];

const NOT_FOUND = "Запрос подтверждения не найден";

const ALREADY_DECIDED = "Запрос подтверждения уже рассмотрен";

// approve по нему отвечает 409 про переезд: иначе второй смысл 409 не увидеть
const MOVED_OUT_ID = 8106;

const daysAgo = (count: number) =>
  new Date(Date.now() - count * 24 * 60 * 60 * 1000).toISOString();

// у третьего дома адрес нарочно длиннее, чем в state.ts: перенос длинной
// строки проверять больше не на чем
const addressOf = (houseId: number): string => {
  if (houseId === 3) {
    return "Республика Татарстан, Казань, ул. Академика Арбузова, д. 16, корпус 2";
  }

  const house = findHouse(houseId);

  return house ? address(house) : "";
};

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
  address: addressOf(fields.house_id),
  status: "pending",
  comment: null,
  reason: null,
  ...fields,
});

// в общем state.ts пользователь один, очереди из разных жителей там не собрать
const seeded: Item[] = [
  seed({
    id: 8101,
    created_at: daysAgo(9),
    house_id: 1,
    flat_number: "12",
    user_name: "Гульнара Ахметзяновна Сафиуллина-Валиева",
    account_no: "1600120088",
    comment:
      "Квитанции приходят на девичью фамилию, в паспорте она другая. Лицевой счёт переписан с последней квитанции за август, но в личном кабинете расчётного центра у него другой номер - там на две цифры длиннее. Подскажите, какой из них правильный, я перезаявлю.",
  }),
  seed({
    id: 8102,
    created_at: daysAgo(7),
    house_id: 2,
    flat_number: "3",
    user_name: "Пётр Сергеев",
    account_no: "1400030077",
    comment: "Купил квартиру в июле, квитанции ещё на прежнего собственника.",
  }),
  seed({
    id: 8103,
    created_at: daysAgo(5),
    house_id: 3,
    flat_number: "118",
    user_name: "Алла Гринёва",
    account_no: "1601180204",
    comment: null,
  }),
  seed({
    id: 8104,
    created_at: daysAgo(4),
    house_id: 1,
    flat_number: "7",
    user_name: "Игорь Тимофеев",
    account_no: "16-00-07-0055",
    comment: "Счёт с квитанции, набрал с дефисами, как напечатано.",
  }),
  seed({
    id: 8105,
    created_at: daysAgo(3),
    house_id: 3,
    flat_number: "204",
    user_name: "Марина Козлова",
    account_no: "1602040311",
    comment: "Живу по договору найма, квитанции забирает собственник.",
  }),
  seed({
    id: MOVED_OUT_ID,
    created_at: daysAgo(2),
    house_id: 2,
    flat_number: "56",
    user_name: "Денис Лапшин",
    account_no: "1400560142",
    comment: "Переехал внутри дома, старую квартиру сдал.",
  }),
  seed({
    id: 8107,
    created_at: daysAgo(1),
    house_id: 1,
    flat_number: "90",
    user_name: "Ольга Белова",
    account_no: "1600900027",
    comment: null,
  }),
  seed({
    id: 8108,
    created_at: daysAgo(1),
    house_id: 3,
    flat_number: "33",
    user_name: "Рустем Хайруллин",
    account_no: "1600330176",
    comment: "Счётчики хочу подавать сам, а не через соседа.",
  }),
  seed({
    id: 8109,
    created_at: daysAgo(6),
    house_id: 1,
    flat_number: "45",
    user_name: "Анна Морозова",
    account_no: "1600450012",
    status: "approved",
    comment: "Квитанция за сентябрь на руках.",
  }),
  seed({
    id: 8110,
    created_at: daysAgo(8),
    house_id: 2,
    flat_number: "11",
    user_name: "Виктор Панов",
    account_no: "0000000000",
    status: "rejected",
    comment: "Номер списал с домофонной карточки.",
    reason: "Лицевой счёт не совпал с данными УК",
  }),
];

const findSeeded = (id: number) => seeded.find((item) => item.id === id);

// настоящие запросы из общего состояния; видна последняя заявка по квартире
const live = () =>
  residencies().flatMap((residency) => {
    const flat =
      residency.flat_id === null ? null : findFlat(residency.flat_id);
    const request = flat ? latestVerification(flat.id) : undefined;

    return flat && request ? [{ residency, flat, request }] : [];
  });

const findLive = (id: number) =>
  live().find((found) => found.request.id === id);

const queue = (): Item[] =>
  [
    ...live().map(({ request, flat }) =>
      verificationRequestItem(request, flat),
    ),
    ...seeded,
    // порядок ответа бэка - created_at DESC
  ].sort((a, b) => b.created_at.localeCompare(a.created_at));

export const adminVerificationsConfigs = [
  {
    path: "/admin/verification-requests" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const status = request.query.status;
        const houseId = number(request.query.house_id);
        const limit = number(request.query.limit) ?? 20;
        const offset = number(request.query.offset) ?? 0;
        const found = queue().filter(
          (item) =>
            (status === undefined || item.status === status) &&
            (houseId === null || item.house_id === houseId),
        );

        return ok({
          items: found.slice(offset, offset + limit),
          total: found.length,
        } satisfies Schemas["Page_VerificationRequestItem_"]);
      }),
    ],
  },
  {
    path: "/admin/verification-requests/:verification_id/approve" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const id = Number(request.params.verification_id);
        const item = findSeeded(id);

        if (item) {
          if (item.status !== "pending") {
            return conflict(ALREADY_DECIDED);
          }

          if (id === MOVED_OUT_ID) {
            return conflict(
              "Житель привязан к другой квартире, переезд оформляет УК",
            );
          }

          item.status = "approved";

          return ok(item);
        }

        const found = findLive(id);

        if (!found) {
          return notFound(NOT_FOUND);
        }

        if (found.request.status !== "pending") {
          return conflict(ALREADY_DECIDED);
        }

        found.request.status = "approved";
        setVerified(found.residency, found.flat.id);

        return ok(verificationRequestItem(found.request, found.flat));
      }),
    ],
  },
  {
    path: "/admin/verification-requests/:verification_id/reject" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const id = Number(request.params.verification_id);
        const reason =
          typeof request.body.reason === "string"
            ? request.body.reason.trim()
            : "";

        if (!reason) {
          return badRequest("Укажите причину отказа");
        }

        const item = findSeeded(id);

        if (item) {
          if (item.status !== "pending") {
            return conflict(ALREADY_DECIDED);
          }

          item.status = "rejected";
          item.reason = reason;

          return ok(item);
        }

        const found = findLive(id);

        if (!found) {
          return notFound(NOT_FOUND);
        }

        if (found.request.status !== "pending") {
          return conflict(ALREADY_DECIDED);
        }

        found.request.status = "rejected";
        found.request.reason = reason;

        return ok(verificationRequestItem(found.request, found.flat));
      }),
    ],
  },
];
