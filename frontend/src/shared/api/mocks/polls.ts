import {
  badRequest,
  conflict,
  forbidden,
  notFound,
  ok,
  route,
  type Reply,
} from "./reply";
import {
  addPollVote,
  createPoll,
  isChairman,
  isOrgStaff,
  findPoll,
  housePolls,
  myVote,
  pollCard,
  pollListItem,
  pollNonVoters,
  pollResults,
  residencyForHouse,
} from "./state";

// опрос виден жителю его дома и сотруднику УК: карточку и результаты кабинет
// УК открывает теми же ручками, что и житель
const pollAccess = (rawPollId: string) => {
  const poll = findPoll(Number(rawPollId));

  if (!poll || !(residencyForHouse(poll.house_id) || isOrgStaff())) {
    return notFound("Опрос не найден");
  }

  return poll;
};

const isReply = (value: unknown): value is Reply =>
  typeof value === "object" && value !== null && "status" in value;

export const pollsConfigs = [
  {
    path: "/houses/:house_id/polls" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const houseId = Number(request.params.house_id);

        if (!residencyForHouse(houseId)) {
          return notFound("Дом не найден");
        }

        return ok(housePolls(houseId).map(pollListItem));
      }),
    ],
  },
  {
    path: "/houses/:house_id/polls" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const houseId = Number(request.params.house_id);
        const residency = residencyForHouse(houseId);

        if (!residency) {
          return notFound("Дом не найден");
        }

        if (!isChairman(residency)) {
          return forbidden("Опрос дома может создать только председатель");
        }

        const title = String(request.body.title ?? "").trim();
        const options = (
          Array.isArray(request.body.options) ? request.body.options : []
        )
          .map((option) => String(option).trim())
          .filter(Boolean);
        const endsAt = String(request.body.ends_at ?? "");

        if (options.length < 2 || new Set(options).size !== options.length) {
          return badRequest("Добавьте минимум два разных варианта ответа");
        }

        if (!title) {
          return badRequest("Укажите заголовок опроса");
        }

        if (new Date(endsAt) <= new Date()) {
          return conflict("Дата окончания опроса должна быть в будущем");
        }

        const description = request.body.description;
        const poll = createPoll(houseId, {
          title,
          description: description == null ? null : String(description),
          options,
          ends_at: endsAt,
          is_multiple: request.body.is_multiple === true,
        });

        return ok(pollCard(poll));
      }),
    ],
  },
  {
    path: "/polls/:poll_id" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const poll = pollAccess(request.params.poll_id);

        return isReply(poll) ? poll : ok(pollCard(poll));
      }),
    ],
  },
  {
    path: "/polls/:poll_id/results" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const poll = pollAccess(request.params.poll_id);

        return isReply(poll) ? poll : ok(pollResults(poll));
      }),
    ],
  },
  {
    path: "/polls/:poll_id/non-voters" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const poll = pollAccess(request.params.poll_id);

        if (isReply(poll)) {
          return poll;
        }

        if (!poll.created_by_me && !isOrgStaff()) {
          return forbidden("Доступно только организатору опроса");
        }

        return ok(pollNonVoters(poll));
      }),
    ],
  },
  {
    path: "/polls/:poll_id/close" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const poll = pollAccess(request.params.poll_id);

        if (isReply(poll)) {
          return poll;
        }

        if (!poll.created_by_me && !isOrgStaff()) {
          return forbidden("Доступно только организатору опроса");
        }

        poll.closed = true;

        return ok(pollCard(poll));
      }),
    ],
  },
  {
    path: "/polls/:poll_id/vote" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const poll = pollAccess(request.params.poll_id);

        if (isReply(poll)) {
          return poll;
        }

        const card = pollCard(poll);
        const residency = residencyForHouse(poll.house_id);

        if (!residency) {
          return notFound("Опрос не найден");
        }

        if (card.status === "closed") {
          return conflict("Опрос завершен");
        }

        if (residency.role === "tenant") {
          return forbidden("Арендатор не участвует в опросах");
        }

        if (myVote(poll)) {
          return conflict("Вы уже проголосовали");
        }

        const chosen = [
          ...new Set(
            Array.isArray(request.body.option_ids)
              ? request.body.option_ids.map(Number)
              : [],
          ),
        ];

        if (chosen.length === 0) {
          return badRequest("Выберите хотя бы один вариант ответа");
        }

        if (
          chosen.some((id) => !poll.options.some((option) => option.id === id))
        ) {
          return badRequest("Вариант не относится к этому опросу");
        }

        if (!poll.is_multiple && chosen.length > 1) {
          return badRequest("В этом опросе можно выбрать только один вариант");
        }

        addPollVote(poll, chosen);

        return ok(pollResults(poll));
      }),
    ],
  },
];
