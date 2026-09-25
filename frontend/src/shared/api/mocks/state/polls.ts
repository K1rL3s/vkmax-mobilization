import type { components } from "../../schema/generated";

import { FLATS } from "./houses";
import { residencyForHouse } from "./profile";
import { days } from "./time";

type Schemas = components["schemas"];

type MockPollVote = {
  is_mine: boolean;
  flat_id: number | null;
  option_ids: number[];
  counted_by_area: boolean;
};

type MockPoll = {
  id: number;
  house_id: number;
  title: string;
  description: string | null;
  created_by_role: string;
  created_by_me: boolean;
  is_multiple: boolean;
  closed: boolean;
  created_at: string;
  ends_at: string;
  options: { id: number; text: string }[];
  votes: MockPollVote[];
};

const options = (firstId: number, texts: string[]) =>
  texts.map((text, index) => ({ id: firstId + index, text }));

const vote = (
  flat_id: number | null,
  option_ids: number[],
  counted_by_area = true,
  is_mine = false,
): MockPollVote => ({ is_mine, flat_id, option_ids, counted_by_area });

const poll = (
  fields: Pick<
    MockPoll,
    "id" | "title" | "created_at" | "ends_at" | "options" | "votes"
  > &
    Partial<MockPoll>,
): MockPoll => ({
  house_id: 1,
  description: null,
  created_by_role: "chairman",
  created_by_me: false,
  is_multiple: false,
  closed: false,
  ...fields,
});

const polls: MockPoll[] = [
  poll({
    id: 301,
    title: "Ремонт подъезда: что делать в первую очередь",
    description:
      "УК выделила смету на один вид работ в этом году. Выберите, с чего начать.",
    created_at: days(-2),
    ends_at: days(2),
    options: options(511, [
      "Покрасить стены",
      "Заменить окна",
      "Починить почтовые ящики",
    ]),
    votes: [
      vote(101, [512], true, true),
      vote(102, [511]),
      vote(103, [512]),
      vote(109, [512]),
      vote(111, [511]),
    ],
  }),
  poll({
    id: 302,
    title: "Установка шлагбаума во дворе",
    description:
      "Двор открыт для сквозного проезда, мест для жителей не хватает.",
    created_by_me: true,
    created_at: days(-4),
    ends_at: days(5),
    options: options(521, ["За", "Против", "Воздержусь"]),
    votes: [vote(102, [521]), vote(107, [521]), vote(110, [521])],
  }),
  poll({
    id: 303,
    title: "Где поставить детскую площадку",
    created_at: days(-6),
    ends_at: days(9),
    options: options(531, ["У первого подъезда", "За домом, у сквера"]),
    votes: [
      vote(102, [531]),
      vote(107, [532]),
      vote(106, [531], false),
      vote(108, [532], false),
      vote(null, [531], false),
    ],
  }),
  poll({
    id: 304,
    title: "Что благоустроить во дворе в этом году",
    description: "Можно выбрать несколько вариантов.",
    is_multiple: true,
    created_at: days(-8),
    ends_at: days(14),
    options: options(541, [
      "Детская площадка",
      "Парковка",
      "Озеленение",
      "Освещение",
    ]),
    votes: [
      vote(102, [541, 543]),
      vote(103, [543]),
      vote(109, [542]),
      vote(110, [541, 544]),
    ],
  }),
  poll({
    id: 305,
    title: "Переход на прямые договоры с ресурсоснабжающими организациями",
    created_by_role: "staff",
    closed: true,
    created_at: days(-20),
    ends_at: days(-3),
    options: options(551, ["Поддерживаю", "Не поддерживаю"]),
    votes: [
      vote(101, [552], true, true),
      vote(102, [551]),
      vote(103, [551]),
      vote(107, [551]),
      vote(109, [551]),
      vote(110, [552]),
      vote(111, [551]),
    ],
  }),
  poll({
    id: 306,
    title: "Смена подрядчика по уборке двора",
    created_by_me: true,
    closed: true,
    created_at: days(-30),
    ends_at: days(-10),
    options: options(561, ["Сменить", "Оставить текущего"]),
    votes: [vote(103, [561]), vote(110, [562])],
  }),
];

let nextPollId = 320;

let nextPollOptionId = 600;

const QUORUM_PERCENT = 5000;

const POLL_DISCLAIMER =
  "предварительный сбор позиций собственников, не является голосованием (ОСС) по ЖК РФ";

const areaPercent = (area: number, totalArea: number): number =>
  totalArea === 0 ? 0 : Math.floor((area * 10000) / totalArea);

const pollStatus = (poll: MockPoll): Schemas["PollStatus"] =>
  poll.closed || new Date(poll.ends_at) <= new Date() ? "closed" : "active";

const weightedFlats = (poll: MockPoll): number[] => [
  ...new Set(
    poll.votes.flatMap((vote) =>
      vote.counted_by_area && vote.flat_id !== null ? [vote.flat_id] : [],
    ),
  ),
];

export const myVote = (poll: MockPoll): MockPollVote | undefined =>
  poll.votes.find((vote) => vote.is_mine);

export const housePolls = (houseId: number): MockPoll[] =>
  polls
    .filter((poll) => poll.house_id === houseId)
    .sort((a, b) => b.created_at.localeCompare(a.created_at) || b.id - a.id)
    .sort(
      (a, b) =>
        Number(pollStatus(a) === "closed") - Number(pollStatus(b) === "closed"),
    );
export const pollListItem = (poll: MockPoll): Schemas["PollListItem"] => ({
  id: poll.id,
  title: poll.title,
  status: pollStatus(poll),
  starts_at: poll.created_at,
  ends_at: poll.ends_at,
  is_multiple: poll.is_multiple,
  voted: myVote(poll) !== undefined,
  voted_flats: weightedFlats(poll).length,
});

export const findPoll = (pollId: number): MockPoll | undefined =>
  polls.find((poll) => poll.id === pollId);

export const pollCard = (poll: MockPoll): Schemas["PollCard"] => {
  const residency = residencyForHouse(poll.house_id);

  return {
    ...pollListItem(poll),
    house_id: poll.house_id,
    created_by_role: poll.created_by_role,
    can_vote:
      residency !== undefined &&
      residency.role === "owner" &&
      pollStatus(poll) === "active",
    can_manage: poll.created_by_me,
    options: poll.options.map((option, index) => ({
      id: option.id,
      text: option.text,
      position: index,
    })),
    disclaimer: POLL_DISCLAIMER,
    description: poll.description,
    my_option_ids: myVote(poll)?.option_ids ?? [],
    is_oss: false,
  };
};

export const pollResults = (poll: MockPoll): Schemas["PollResults"] => {
  const flats = FLATS.filter((flat) => flat.house_id === poll.house_id);
  const areaOf = (flatId: number) =>
    flats.find((flat) => flat.id === flatId)?.area ?? null;
  const totalArea = flats.reduce((sum, flat) => sum + (flat.area ?? 0), 0);
  const votedIds = weightedFlats(poll);
  const votedArea = votedIds.reduce((sum, id) => sum + (areaOf(id) ?? 0), 0);
  const percent = areaPercent(votedArea, totalArea);

  return {
    poll_id: poll.id,
    status: pollStatus(poll),
    total_flats: flats.length,
    voted_flats: votedIds.length,
    total_area: totalArea,
    voted_area: votedArea,
    voted_area_percent: percent,
    quorum_percent: QUORUM_PERCENT,
    quorum_reached: percent >= QUORUM_PERCENT,
    unverified_flats: poll.votes.filter((vote) => !vote.counted_by_area).length,
    options: poll.options.map((option) => {
      const optionFlats = [
        ...new Set(
          poll.votes.flatMap((vote) =>
            vote.counted_by_area &&
            vote.flat_id !== null &&
            vote.option_ids.includes(option.id)
              ? [vote.flat_id]
              : [],
          ),
        ),
      ];
      const area = optionFlats.reduce((sum, id) => sum + (areaOf(id) ?? 0), 0);

      return {
        option_id: option.id,
        text: option.text,
        flats_count: optionFlats.length,
        area,
        area_percent: areaPercent(area, totalArea),
      };
    }),
    disclaimer: POLL_DISCLAIMER,
    is_oss: false,
    flats_without_area: flats.filter((flat) => flat.area === null).length,
  };
};

export const addPollVote = (poll: MockPoll, optionIds: number[]): void => {
  const residency = residencyForHouse(poll.house_id);
  const flatId = residency?.flat_id ?? null;

  poll.votes.push(
    vote(
      flatId,
      optionIds,
      residency?.verified === true &&
        flatId !== null &&
        !weightedFlats(poll).includes(flatId),
      true,
    ),
  );
};

export const pollNonVoters = (
  poll: MockPoll,
): Schemas["PollNonVoterItem"][] => {
  const voted = weightedFlats(poll);

  return FLATS.filter(
    (flat) => flat.house_id === poll.house_id && !voted.includes(flat.id),
  )
    .sort(
      (a, b) =>
        Number(a.entrance === null) - Number(b.entrance === null) ||
        (a.entrance ?? 0) - (b.entrance ?? 0) ||
        a.number.length - b.number.length ||
        a.number.localeCompare(b.number, "ru"),
    )
    .map((flat) => ({
      flat_id: flat.id,
      flat_number: flat.number,
      entrance: flat.entrance,
    }));
};

export const createPoll = (
  houseId: number,
  draft: Pick<
    MockPoll,
    "title" | "description" | "ends_at" | "is_multiple" | "created_by_role"
  > & { options: string[] },
): MockPoll => {
  const created = poll({
    ...draft,
    id: nextPollId++,
    house_id: houseId,
    created_by_me: true,
    created_at: new Date().toISOString(),
    options: options(nextPollOptionId, draft.options),
    votes: [],
  });
  nextPollOptionId += draft.options.length;
  polls.push(created);

  return created;
};
