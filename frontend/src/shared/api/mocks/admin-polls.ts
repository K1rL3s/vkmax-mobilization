import type { components } from "../schema/generated";

import { pollOptions } from "./polls";
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
  createPoll,
  housePolls,
  pollCard,
  pollListItem,
} from "./state";

type Schemas = components["schemas"];

const ORG_HOUSE_IDS = [1, 2, 3];

export const adminPollsConfigs = [
  endpoint("get", "/admin/polls", (request) => {
    const status = request.query.status;
    const houseId = number(request.query.house_id);
    const found = page(
      ORG_HOUSE_IDS.flatMap((id) =>
        housePolls(id).map((poll) => ({
          ...pollListItem(poll),
          house_id: id,
          address: addressOf(id),
        })),
      )
        .sort(
          (a, b) =>
            Number(a.status === "closed") - Number(b.status === "closed") ||
            b.starts_at.localeCompare(a.starts_at) ||
            b.id - a.id,
        )
        .filter(
          (item) =>
            (status === undefined || item.status === status) &&
            (houseId === null || item.house_id === houseId),
        ),
      request.query,
    );

    return houseId !== null && !ORG_HOUSE_IDS.includes(houseId)
      ? notFound("Дом не найден")
      : ok(found satisfies Schemas["Page_AdminPollListItem_"]);
  }),
  endpoint("post", "/admin/polls", (request) => {
    const houseId = Number(request.body.house_id);

    if (!ORG_HOUSE_IDS.includes(houseId)) {
      return notFound("Дом не найден");
    }

    const options = pollOptions(request.body.options);
    const endsAt = String(request.body.ends_at ?? "");

    if (options.length < 2 || new Set(options).size !== options.length) {
      return badRequest("Добавьте минимум два разных варианта ответа");
    }

    if (!(new Date(endsAt) > new Date())) {
      return conflict("Дата окончания опроса должна быть в будущем");
    }

    const description = request.body.description;

    return ok(
      pollCard(
        createPoll(houseId, {
          title: String(request.body.title ?? "").trim(),
          description: description == null ? null : String(description),
          options,
          ends_at: endsAt,
          is_multiple: request.body.is_multiple === true,
          created_by_role: "staff",
        }),
      ),
    );
  }),
];
