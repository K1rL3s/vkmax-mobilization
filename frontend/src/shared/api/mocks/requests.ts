import type { components } from "../schema/generated";

import { readUploadedFile } from "./multipart";
import {
  badRequest,
  conflict,
  endpoint,
  forbidden,
  houseOf,
  notFound,
  ok,
  page,
} from "./reply";
import {
  createRequest,
  findRequest,
  houseRequests,
  nextFileName,
  repeatRequest,
  requestCard,
  requestCategories,
  requestListItem,
  similarRequests,
  uploads,
} from "./state";

type Schemas = components["schemas"];

const STATUSES: Schemas["RequestStatus"][] = [
  "new",
  "accepted",
  "in_progress",
  "on_review",
  "done",
];

const categoryOf = (value: string | undefined) =>
  requestCategories().find(({ category }) => category === value)?.category;

const CLASSIFY_RULES: [RegExp, Schemas["RequestCategory"]][] = [
  [/теч|капает|залива|потоп/i, "leak"],
  [/лифт/i, "elevator"],
  [/мусор|контейнер/i, "garbage"],
  [/батаре|отоплен/i, "heating"],
  [/нет (горячей |холодной )?воды|напор/i, "water_supply"],
  [/свет|ламп|электр|розетк/i, "electricity"],
  [/подъезд|двер|стекл|домофон/i, "entrance"],
  [/двор|яма|площадк|парковк/i, "yard"],
];

export const requestsConfigs = [
  endpoint("post", "/requests/classify", (request) => {
    const text = String(request.body.text ?? "");
    const category =
      CLASSIFY_RULES.find(([pattern]) => pattern.test(text))?.[1] ?? null;

    return ok({
      category,
      zone:
        requestCategories().find((item) => item.category === category)?.zone ??
        null,
    } satisfies Schemas["ClassifyRequestResponse"]);
  }),
  endpoint("get", "/requests", (request) => {
    const houseId = houseOf(request);

    if (houseId === null) {
      return forbidden("Укажите X-House-Id");
    }

    const status =
      STATUSES.find((value) => value === request.query.status) ?? null;

    return ok(
      page(houseRequests(houseId, status).map(requestListItem), request.query),
    );
  }),
  endpoint("post", "/requests", (request) => {
    const houseId = houseOf(request);

    if (houseId === null) {
      return forbidden("Укажите X-House-Id");
    }

    const body = request.body as Schemas["CreateRequestRequest"];

    return categoryOf(body.category) && body.description?.trim()
      ? ok(requestCard(createRequest(houseId, body)))
      : badRequest("Опишите проблему и выберите категорию");
  }),
  endpoint("get", "/requests/similar", (request) => {
    const houseId = houseOf(request);
    const category = categoryOf(request.query.category);

    return houseId === null || !category
      ? badRequest("Укажите дом и категорию")
      : ok(similarRequests(houseId, category));
  }),
  endpoint("get", "/requests/:request_id", (request) => {
    const item = findRequest(Number(request.params.request_id));

    return item ? ok(requestCard(item)) : notFound("Заявка не найдена");
  }),
  endpoint("post", "/requests/:request_id/rating", (request) => {
    const item = findRequest(Number(request.params.request_id));

    if (!item) {
      return notFound("Заявка не найдена");
    }

    if (item.status !== "done" || item.rating !== null) {
      return badRequest("Заявку сейчас нельзя оценить");
    }

    const body = request.body as Schemas["RateRequestRequest"];

    if (!Number.isInteger(body.rating) || body.rating < 1 || body.rating > 5) {
      return badRequest("Оценка - от 1 до 5");
    }

    item.rating = body.rating;
    item.feedback = body.feedback ?? null;

    return ok(requestCard(item));
  }),
  endpoint("post", "/requests/:request_id/accept", (request) => {
    const item = findRequest(Number(request.params.request_id));

    if (!item) {
      return notFound("Заявка не найдена");
    }

    if (item.status !== "on_review") {
      return conflict("Заявка не на приёмке");
    }

    item.status = "done";
    item.completion_reason = "resident_accepted";

    return ok(requestCard(item));
  }),
  endpoint("post", "/requests/:request_id/repeat", (request) => {
    const item = findRequest(Number(request.params.request_id));

    if (!item) {
      return notFound("Заявка не найдена");
    }

    if (item.status !== "done" && item.status !== "on_review") {
      return conflict("Повтор заводится по завершённой заявке");
    }

    const body = request.body as Schemas["RepeatRequestRequest"];
    const description = body.description?.trim() || null;

    if (item.status === "on_review") {
      if (!description) {
        return badRequest("Опишите, что не так с работой");
      }

      item.status = "done";
      item.completion_reason = "resident_rejected";
    }

    return ok(requestCard(repeatRequest(item, description, body.photos ?? [])));
  }),
  endpoint("get", "/request-categories", () => ok(requestCategories())),
  endpoint("post", "/files", async (request) => {
    const name = nextFileName();
    const url = await readUploadedFile(request);

    if (!url) {
      return badRequest("Файл не пришёл");
    }

    uploads.set(name, url);

    return ok({ name, url });
  }),
];
