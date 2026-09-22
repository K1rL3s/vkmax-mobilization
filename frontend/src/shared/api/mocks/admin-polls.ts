import type { components } from "../schema/generated";

import { badRequest, conflict, notFound, number, ok, route } from "./reply";
import {
  address,
  createPoll,
  findHouse,
  housePolls,
  pollCard,
  pollListItem,
} from "./state";

type Schemas = components["schemas"];

// дома ООО «Жилсервис», как в admin-houses.ts; X-Org-Id мок не сверяет
const ORG_HOUSE_IDS = [1, 2, 3];

const orgPolls = () =>
  ORG_HOUSE_IDS.flatMap((houseId) => {
    const house = findHouse(houseId);

    return house
      ? housePolls(houseId).map((poll) => ({
          ...pollListItem(poll),
          house_id: houseId,
          address: address(house),
        }))
      : [];
  })
    // порядок бэка: идущие перед завершёнными, внутри свежие сверху
    .sort(
      (a, b) =>
        Number(a.status === "closed") - Number(b.status === "closed") ||
        b.starts_at.localeCompare(a.starts_at) ||
        b.id - a.id,
    );

export const adminPollsConfigs = [
  {
    path: "/admin/polls" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const status = request.query.status;
        const houseId = number(request.query.house_id);
        const limit = number(request.query.limit) ?? 20;
        const offset = number(request.query.offset) ?? 0;

        if (houseId !== null && !ORG_HOUSE_IDS.includes(houseId)) {
          return notFound("Дом не найден");
        }

        const found = orgPolls().filter(
          (item) =>
            (status === undefined || item.status === status) &&
            (houseId === null || item.house_id === houseId),
        );

        return ok({
          items: found.slice(offset, offset + limit),
          total: found.length,
        } satisfies Schemas["Page_AdminPollListItem_"]);
      }),
    ],
  },
  {
    path: "/admin/polls" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const houseId = Number(request.body.house_id);

        if (!ORG_HOUSE_IDS.includes(houseId)) {
          return notFound("Дом не найден");
        }

        const options = (
          Array.isArray(request.body.options) ? request.body.options : []
        )
          .map((option) => String(option).trim())
          .filter(Boolean);
        const endsAt = String(request.body.ends_at ?? "");

        if (options.length < 2 || new Set(options).size !== options.length) {
          return badRequest("Добавьте минимум два разных варианта ответа");
        }

        if (!(new Date(endsAt) > new Date())) {
          return conflict("Дата окончания опроса должна быть в будущем");
        }

        const description = request.body.description;
        const poll = createPoll(houseId, {
          title: String(request.body.title ?? "").trim(),
          description: description == null ? null : String(description),
          options,
          ends_at: endsAt,
          is_multiple: request.body.is_multiple === true,
        });

        // createPoll из state.ts пишет роль председателя, а опрос от
        // организации бэк помечает как staff
        poll.created_by_role = "staff";

        return ok(pollCard(poll));
      }),
    ],
  },
];
