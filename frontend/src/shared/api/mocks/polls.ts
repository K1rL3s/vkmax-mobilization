import {
  badRequest,
  conflict,
  endpoint,
  forbidden,
  isReply,
  notFound,
  ok,
  type MockHttpRequest,
} from "./reply";
import {
  addPollVote,
  createPoll,
  findPoll,
  housePolls,
  isChairman,
  isOrgStaff,
  myVote,
  pollCard,
  pollListItem,
  pollNonVoters,
  pollResults,
  residencyForHouse,
} from "./state";

const pollAccess = (request: MockHttpRequest) => {
  const poll = findPoll(Number(request.params.poll_id));

  return poll && (residencyForHouse(poll.house_id) || isOrgStaff())
    ? poll
    : notFound("Опрос не найден");
};

const managedPoll = (request: MockHttpRequest) => {
  const poll = pollAccess(request);

  return isReply(poll) || poll.created_by_me || isOrgStaff()
    ? poll
    : forbidden("Доступно только организатору опроса");
};

export const pollOptions = (value: unknown) =>
  (Array.isArray(value) ? value : [])
    .map((option) => String(option).trim())
    .filter(Boolean);

export const pollsConfigs = [
  endpoint("get", "/houses/:house_id/polls", (request) => {
    const houseId = Number(request.params.house_id);

    return residencyForHouse(houseId)
      ? ok(housePolls(houseId).map(pollListItem))
      : notFound("Дом не найден");
  }),
  endpoint("post", "/houses/:house_id/polls", (request) => {
    const houseId = Number(request.params.house_id);
    const residency = residencyForHouse(houseId);

    if (!residency) {
      return notFound("Дом не найден");
    }

    if (!isChairman(residency)) {
      return forbidden("Опрос дома может создать только председатель");
    }

    const title = String(request.body.title ?? "").trim();
    const options = pollOptions(request.body.options);
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

    return ok(
      pollCard(
        createPoll(houseId, {
          title,
          description: description == null ? null : String(description),
          options,
          ends_at: endsAt,
          is_multiple: request.body.is_multiple === true,
          created_by_role: "chairman",
        }),
      ),
    );
  }),
  endpoint("get", "/polls/:poll_id", (request) => {
    const poll = pollAccess(request);

    return isReply(poll) ? poll : ok(pollCard(poll));
  }),
  endpoint("get", "/polls/:poll_id/results", (request) => {
    const poll = pollAccess(request);

    return isReply(poll) ? poll : ok(pollResults(poll));
  }),
  endpoint("get", "/polls/:poll_id/non-voters", (request) => {
    const poll = managedPoll(request);

    return isReply(poll) ? poll : ok(pollNonVoters(poll));
  }),
  endpoint("post", "/polls/:poll_id/close", (request) => {
    const poll = managedPoll(request);

    if (isReply(poll)) {
      return poll;
    }

    poll.closed = true;

    return ok(pollCard(poll));
  }),
  endpoint("post", "/polls/:poll_id/vote", (request) => {
    const poll = pollAccess(request);

    if (isReply(poll)) {
      return poll;
    }

    const residency = residencyForHouse(poll.house_id);

    if (!residency) {
      return notFound("Опрос не найден");
    }

    if (pollListItem(poll).status === "closed") {
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

    if (chosen.some((id) => !poll.options.some((option) => option.id === id))) {
      return badRequest("Вариант не относится к этому опросу");
    }

    if (!poll.is_multiple && chosen.length > 1) {
      return badRequest("В этом опросе можно выбрать только один вариант");
    }

    addPollVote(poll, chosen);

    return ok(pollResults(poll));
  }),
];
