import type { components } from "../schema/generated";

import { readUploadedFile } from "./multipart";
import {
  badRequest,
  conflict,
  forbidden,
  notFound,
  number,
  ok,
  route,
} from "./reply";
import {
  acceptRequest,
  createRequest,
  findRequest,
  houseRequests,
  nextFileName,
  rateRequest,
  rejectRequest,
  repeatRequest,
  requestCard,
  requestCategories,
  requestListItem,
  residencies,
  saveFile,
  similarRequests,
  type MockHttpRequest,
} from "./state";

type Schemas = components["schemas"];

const STATUSES: Schemas["RequestStatus"][] = [
  "new",
  "accepted",
  "in_progress",
  "on_review",
  "done",
];

// дом запроса: житель одного дома может заголовок не слать, житель нескольких
// обязан - бэк отбивает такой запрос, и мок отбивает его так же
const houseOf = (request: MockHttpRequest): number | null =>
  number(request.headers["x-house-id"]) ??
  residencies().at(-1)?.house_id ??
  null;

const categoryOf = (value: string | undefined) =>
  requestCategories().find(({ category }) => category === value)?.category;

export const requestsConfigs = [
  {
    path: "/requests" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const houseId = houseOf(request);

        if (houseId === null) {
          return forbidden("Укажите X-House-Id");
        }

        const limit = number(request.query.limit) ?? 20;
        const offset = number(request.query.offset) ?? 0;
        const status =
          STATUSES.find((value) => value === request.query.status) ?? null;
        const found = houseRequests(houseId, status);

        return ok({
          items: found.slice(offset, offset + limit).map(requestListItem),
          total: found.length,
        });
      }),
    ],
  },
  {
    path: "/requests" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const houseId = houseOf(request);

        if (houseId === null) {
          return forbidden("Укажите X-House-Id");
        }

        const body = request.body as Schemas["CreateRequestRequest"];

        if (!categoryOf(body.category) || !body.description?.trim()) {
          return badRequest("Опишите проблему и выберите категорию");
        }

        return ok(requestCard(createRequest(houseId, body)));
      }),
    ],
  },
  {
    path: "/requests/similar" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const houseId = houseOf(request);
        const category = categoryOf(request.query.category);

        if (houseId === null || !category) {
          return badRequest("Укажите дом и категорию");
        }

        return ok(similarRequests(houseId, category));
      }),
    ],
  },
  {
    path: "/requests/:request_id" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const item = findRequest(Number(request.params.request_id));

        return item ? ok(requestCard(item)) : notFound("Заявка не найдена");
      }),
    ],
  },
  {
    path: "/requests/:request_id/rating" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const item = findRequest(Number(request.params.request_id));

        if (!item) {
          return notFound("Заявка не найдена");
        }

        if (item.status !== "done" || item.rating !== null) {
          return badRequest("Заявку сейчас нельзя оценить");
        }

        const body = request.body as Schemas["RateRequestRequest"];

        if (
          !Number.isInteger(body.rating) ||
          body.rating < 1 ||
          body.rating > 5
        ) {
          return badRequest("Оценка - от 1 до 5");
        }

        return ok(
          requestCard(rateRequest(item, body.rating, body.feedback ?? null)),
        );
      }),
    ],
  },
  {
    path: "/requests/:request_id/accept" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const item = findRequest(Number(request.params.request_id));

        if (!item) {
          return notFound("Заявка не найдена");
        }

        if (item.status !== "on_review") {
          return conflict("Заявка не на приёмке");
        }

        return ok(requestCard(acceptRequest(item)));
      }),
    ],
  },
  {
    path: "/requests/:request_id/repeat" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const item = findRequest(Number(request.params.request_id));

        if (!item) {
          return notFound("Заявка не найдена");
        }

        if (item.status !== "done" && item.status !== "on_review") {
          return conflict("Повтор заводится по завершённой заявке");
        }

        const body = request.body as Schemas["RepeatRequestRequest"];
        const description = body.description?.trim() || null;

        // отказ от результата обязан объяснить исполнителю, что не так:
        // это описание становится текстом повтора
        if (item.status === "on_review") {
          if (!description) {
            return badRequest("Опишите, что не так с работой");
          }

          rejectRequest(item);
        }

        return ok(
          requestCard(repeatRequest(item, description, body.photos ?? [])),
        );
      }),
    ],
  },
  {
    path: "/request-categories" as const,
    method: "get" as const,
    routes: [route(() => ok(requestCategories()))],
  },
  {
    path: "/files" as const,
    method: "post" as const,
    routes: [
      route(async (request) => {
        const name = nextFileName();
        const url = await readUploadedFile(request);

        if (!url) {
          return badRequest("Файл не пришёл");
        }

        saveFile(name, url);

        return ok({ name, url });
      }),
    ],
  },
];
