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
  canDemoExpire,
  createRequest,
  findRequest,
  houseRequests,
  minutes,
  nextFileName,
  repeatRequest,
  requestCard,
  requestCategories,
  requestListItem,
  similarRequests,
  uploads,
  user,
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

const checkAttachments = (names: string[]): string | null => {
  if (names.length > 12) return "Можно приложить не больше 12 файлов";
  if (names.filter((name) => /\.(mp4|mov)$/.test(name)).length > 2)
    return "Можно приложить не больше 2 видео";
  return null;
};

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
      danger: /пахнет газом/i.test(text) ? "gas" : null,
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
    const mediaError = checkAttachments(body.photos ?? []);
    if (mediaError) return badRequest(mediaError);

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
    const mediaError = checkAttachments(body.photos ?? []);
    if (mediaError) return badRequest(mediaError);

    if (item.status === "on_review") {
      if (!description) {
        return badRequest("Опишите, что не так с работой");
      }

      if (
        !body.photos?.length &&
        !["meter_error", "charge_dispute"].includes(item.category)
      ) {
        return badRequest("Приложите фото: так УК увидит, что не так");
      }

      item.status = "done";
      item.completion_reason = "resident_rejected";
    }

    return ok(requestCard(repeatRequest(item, description, body.photos ?? [])));
  }),
  endpoint("post", "/requests/:request_id/demo/expire", (request) => {
    const item = findRequest(Number(request.params.request_id));

    if (!item || !canDemoExpire(item)) {
      return notFound("Заявка не найдена");
    }

    item.deadline_at = minutes(-1);

    return ok(requestCard(item));
  }),
  endpoint("post", "/requests/:request_id/escalate", (request) => {
    const item = findRequest(Number(request.params.request_id));

    if (!item) {
      return notFound("Заявка не найдена");
    }

    if (
      item.escalated_at !== null ||
      !["new", "accepted", "in_progress"].includes(item.status) ||
      item.deadline_at === null ||
      new Date(item.deadline_at).getTime() > Date.now()
    ) {
      return conflict("Руководство УК уже уведомлено или срок еще идет");
    }

    item.escalated_at = new Date().toISOString();

    return ok(requestCard(item));
  }),
  endpoint("post", "/requests/:request_id/cancel", (request) => {
    const item = findRequest(Number(request.params.request_id));

    if (!item) {
      return notFound("Заявка не найдена");
    }

    if (!["new", "accepted", "in_progress"].includes(item.status)) {
      return conflict("Отменить можно, пока работу не сдали на приемку");
    }

    const body = request.body as Schemas["CancelRequestRequest"];
    if (body.reason === "other" && !body.comment?.trim()) {
      return badRequest("Расскажите, почему отменяете заявку");
    }

    item.status = "done";
    item.completion_reason = "resident_canceled";

    return ok(requestCard(item));
  }),
  endpoint("post", "/requests/:request_id/chat-card", (request) => {
    const item = findRequest(Number(request.params.request_id));

    if (!item) {
      return notFound("Заявка не найдена");
    }

    if (item.status === "done" || item.status === "on_review") {
      return conflict("Заявку на приемке или закрытую соседям уже не показать");
    }

    const shared: Schemas["SharedRequestResponse"] = {
      posted: false,
      share_text: `Заявка №${item.id}. Если у вас то же самое, присоединяйтесь к заявке`,
      share_link: `https://max.ru/zheka_bot?startapp=house_${item.house_id}_${item.category}`,
    };

    return ok(shared);
  }),
  endpoint("get", "/request-categories", () => ok(requestCategories())),
  endpoint("post", "/files", async (request) => {
    const url = await readUploadedFile(request);

    if (!url) {
      return badRequest("Файл не пришёл");
    }

    const mime = /^data:([^;]+);/.exec(url)?.[1] ?? "";
    const suffix = (
      {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/heic": "heic",
        "video/mp4": "mp4",
        "video/quicktime": "mov",
      } as Record<string, string>
    )[mime];
    if (!suffix)
      return badRequest(
        "Поддерживаются только изображения и видео MP4 или MOV",
      );
    const is_video = mime.startsWith("video/");
    const size = atob(url.slice(url.indexOf(",") + 1)).length;
    const limit = is_video ? 50 : 10;
    if (size > limit * 1024 * 1024)
      return badRequest(`${is_video ? "Видео" : "Файл"} больше ${limit} МБ`);
    const name = nextFileName(suffix);
    uploads.set(name, url);

    return ok({ name, url, is_video } satisfies Schemas["FileRef"]);
  }),
  endpoint("get", "/pp290", () => {
    const lift =
      "Работы, выполняемые в целях надлежащего содержания и ремонта лифта (лифтов) в многоквартирном доме";
    const emergency =
      "Обеспечение устранения аварий в соответствии с установленными предельными сроками на внутридомовых инженерных системах в многоквартирном доме, выполнения заявок населения";

    return ok({
      source: "pp_290",
      edition: "в ред. постановления Правительства РФ от 07.03.2025 № 293",
      checked_at: "2026-09-29",
      note: "Мок: два пункта из backend/zheka/core/pp290.json",
      items: [
        {
          ref: "п. 22, абз. 2",
          section: lift,
          text: "организация системы диспетчерского контроля и обеспечение диспетчерской связи с кабиной лифта",
        },
        {
          ref: "п. 22, абз. 3",
          section: lift,
          text: "обеспечение проведения осмотров, технического обслуживания и ремонт лифта (лифтов)",
        },
        {
          ref: "п. 22, абз. 4",
          section: lift,
          text: "обеспечение проведения аварийного обслуживания лифта (лифтов)",
        },
        {
          ref: "п. 22, абз. 5",
          section: lift,
          text: "обеспечение проведения технического освидетельствования лифта (лифтов), в том числе после замены элементов оборудования",
        },
        { ref: "п. 28", section: emergency, text: emergency },
      ],
    } satisfies Schemas["Pp290Catalog"]);
  }),
  endpoint("post", "/requests/:request_id/gji-pdf", (request) => {
    const item = findRequest(Number(request.params.request_id));

    if (!item) {
      return notFound("Заявка не найдена");
    }

    if (
      !["new", "accepted", "in_progress"].includes(item.status) ||
      item.deadline_at === null ||
      new Date(item.deadline_at).getTime() > Date.now()
    ) {
      return conflict(
        "Жалобу в ГЖИ готовим, только когда срок открытой заявки истек",
      );
    }

    return ok({ ok: true } satisfies Schemas["OkResponse"]);
  }),
];
