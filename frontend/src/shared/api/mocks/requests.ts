import type { components } from "../schema/generated";

import { badRequest, forbidden, notFound, number, ok, route } from "./reply";
import {
  createRequest,
  findRequest,
  houseRequests,
  nextFileName,
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
    path: "/request-categories" as const,
    method: "get" as const,
    routes: [route(() => ok(requestCategories()))],
  },
  {
    path: "/files" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const name = nextFileName();
        // multipart мок-сервер не разбирает: тела у такого запроса нет, и
        // вернуть содержимое принятого файла он не может. Превью в мастере
        // всё равно локальное, а на приёмке фото жителя будет заглушкой
        const file = (request.body as { file?: unknown } | undefined)?.file;

        if (typeof file === "string" && file.startsWith("data:")) {
          saveFile(name, file);

          return ok({ name, url: file });
        }

        return ok({ name, url: `/files/${name}` });
      }),
    ],
  },
];
