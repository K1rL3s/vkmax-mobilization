import type { components } from "../../schema/generated";

type Schemas = components["schemas"];

import { FLATS } from "./houses";
import { seedPolls, type MockPoll, type MockPollVote } from "./polls-seed";
import { residencyForHouse } from "./profile";

// порог кворума и дисклеймер приходят полями ответа, фронт их не зашивает
const QUORUM_PERCENT = 5000;

const POLL_DISCLAIMER =
  "предварительный сбор позиций собственников, не является голосованием (ОСС) по ЖК РФ";

// доля в сотых долях процента: площадь * 10000 / площадь дома
const areaPercent = (area: number, totalArea: number): number =>
  totalArea === 0 ? 0 : Math.floor((area * 10000) / totalArea);

const pollStatus = (poll: MockPoll): Schemas["PollStatus"] =>
  poll.closed || new Date(poll.ends_at) <= new Date() ? "closed" : "active";

// вес считает квартиры, а не голоса: у квартиры один голос, и голос без веса
// в счёт не идёт вовсе
const weightedFlats = (poll: MockPoll): number[] => [
  ...new Set(
    poll.votes.flatMap((vote) =>
      vote.counted_by_area && vote.flat_id !== null ? [vote.flat_id] : [],
    ),
  ),
];

const state = {
  polls: seedPolls(),
  nextPollId: 320,
  nextPollOptionId: 600,
};

export const resetPolls = (): void => {
  state.polls = seedPolls();
  state.nextPollId = 320;
  state.nextPollOptionId = 600;
};

export const myVote = (poll: MockPoll): MockPollVote | undefined =>
  poll.votes.find((vote) => vote.is_mine);

export const housePolls = (houseId: number): MockPoll[] => {
  const items = state.polls.filter((poll) => poll.house_id === houseId);

  // порядок задаёт бэк, фронт его не пересортировывает: свежие сверху, идущие
  // опросы перед завершёнными
  items.sort((a, b) => b.created_at.localeCompare(a.created_at) || b.id - a.id);
  items.sort(
    (a, b) =>
      Number(pollStatus(a) === "closed") - Number(pollStatus(b) === "closed"),
  );

  return items;
};

export const pollListItem = (poll: MockPoll): Schemas["PollListItem"] => ({
  id: poll.id,
  title: poll.title,
  status: pollStatus(poll),
  // опрос начинается в момент создания, отдельной даты старта у него нет
  starts_at: poll.created_at,
  ends_at: poll.ends_at,
  is_multiple: poll.is_multiple,
  voted: myVote(poll) !== undefined,
  voted_flats: weightedFlats(poll).length,
});

export const findPoll = (pollId: number): MockPoll | undefined =>
  state.polls.find((poll) => poll.id === pollId);

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
    // мнение без веса считается по голосующему, а не по квартире: у квартиры
    // без веса квартиры и нет
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

  poll.votes = [
    ...poll.votes,
    {
      is_mine: true,
      flat_id: flatId,
      option_ids: optionIds,
      // вес даёт подтверждённая квартира, за которую ещё никто не голосовал
      counted_by_area:
        residency?.verified === true &&
        flatId !== null &&
        !weightedFlats(poll).includes(flatId),
    },
  ];
};

export const pollNonVoters = (
  poll: MockPoll,
): Schemas["PollNonVoterItem"][] => {
  const voted = weightedFlats(poll);
  const items = FLATS.filter(
    (flat) => flat.house_id === poll.house_id && !voted.includes(flat.id),
  );

  // порядок задаёт бэк: по подъездам, квартиры без подъезда в конце
  items.sort(
    (a, b) =>
      Number(a.entrance === null) - Number(b.entrance === null) ||
      (a.entrance ?? 0) - (b.entrance ?? 0) ||
      a.number.localeCompare(b.number, "ru"),
  );

  return items.map((flat) => ({
    flat_id: flat.id,
    flat_number: flat.number,
    entrance: flat.entrance,
  }));
};

export const createPoll = (
  houseId: number,
  draft: {
    title: string;
    description: string | null;
    options: string[];
    ends_at: string;
    is_multiple: boolean;
  },
): MockPoll => {
  const now = new Date().toISOString();
  const poll: MockPoll = {
    id: state.nextPollId,
    house_id: houseId,
    title: draft.title,
    description: draft.description,
    created_by_role: "chairman",
    created_by_me: true,
    is_multiple: draft.is_multiple,
    closed: false,
    created_at: now,
    ends_at: draft.ends_at,
    options: draft.options.map((text, index) => ({
      id: state.nextPollOptionId + index,
      text,
    })),
    votes: [],
  };

  state.nextPollId += 1;
  state.nextPollOptionId += draft.options.length;
  state.polls = [...state.polls, poll];

  return poll;
};
