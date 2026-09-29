import type { components } from "../schema/generated";

import {
  badRequest,
  conflict,
  endpoint,
  forbidden,
  notFound,
  ok,
  type MockHttpRequest,
} from "./reply";
import {
  days,
  findHouse,
  findPoll,
  isChairman,
  residencyForHouse,
} from "./state";

type MockProposal = components["schemas"]["ProposalItem"] & {
  house_id: number;
  mine: boolean;
};

const PER_DAY = 3;

const proposals: MockProposal[] = [
  {
    id: 401,
    created_at: days(-3),
    text: "Поставить лавочку и урну у третьего подъезда: сидеть негде, окурки летят в газон.",
    status: "new",
    answer: null,
    answered_at: null,
    poll_id: null,
    house_id: 1,
    mine: false,
  },
  {
    id: 402,
    created_at: days(-9),
    text: "Закрывать калитку со стороны школы на ночь.",
    status: "declined",
    answer: "Калитка эвакуационная, закрывать её нельзя.",
    answered_at: days(-8),
    poll_id: null,
    house_id: 1,
    mine: false,
  },
];

let nextProposalId = 420;

const inHouse = (houseId: number) =>
  proposals.filter((proposal) => proposal.house_id === houseId);

const mineIn = (houseId: number) =>
  inHouse(houseId).filter((proposal) => proposal.mine);

const hasChairman = (houseId: number) =>
  findHouse(houseId)?.is_connected === true;

const item = (
  proposal: MockProposal,
): components["schemas"]["ProposalItem"] => ({
  id: proposal.id,
  created_at: proposal.created_at,
  text: proposal.text,
  status: proposal.status,
  answer: proposal.answer,
  answered_at: proposal.answered_at,
  poll_id: proposal.poll_id,
});

const chairmanOf = (request: MockHttpRequest) => {
  const houseId = Number(request.params.house_id);
  const residency = residencyForHouse(houseId);

  return residency && isChairman(residency)
    ? houseId
    : forbidden("Предложения совету дома читает председатель");
};

export const proposalsConfigs = [
  endpoint("post", "/houses/:house_id/proposals", (request) => {
    const houseId = Number(request.params.house_id);

    if (!residencyForHouse(houseId)) {
      return notFound("Дом не найден");
    }

    if (!hasChairman(houseId)) {
      return conflict("В доме пока нет председателя совета");
    }

    const text = String(request.body.text ?? "").trim();

    if (text.length < 10 || text.length > 1000) {
      return badRequest("Предложение должно быть от 10 до 1000 символов");
    }

    if (mineIn(houseId).length >= PER_DAY) {
      return conflict(`Больше ${PER_DAY} предложений в сутки отправить нельзя`);
    }

    const created: MockProposal = {
      id: nextProposalId++,
      created_at: new Date().toISOString(),
      text,
      status: "new",
      answer: null,
      answered_at: null,
      poll_id: null,
      house_id: houseId,
      mine: true,
    };
    proposals.unshift(created);

    return ok(item(created));
  }),
  endpoint("get", "/houses/:house_id/proposals/my", (request) => {
    const houseId = Number(request.params.house_id);

    if (!residencyForHouse(houseId)) {
      return notFound("Дом не найден");
    }

    return ok({
      has_chairman: hasChairman(houseId),
      items: mineIn(houseId).map(item),
    });
  }),
  endpoint("get", "/houses/:house_id/proposals", (request) => {
    const house = chairmanOf(request);

    return typeof house === "number" ? ok(inHouse(house).map(item)) : house;
  }),
  endpoint("post", "/proposals/:proposal_id/answer", (request) => {
    const proposal = proposals.find(
      (candidate) => candidate.id === Number(request.params.proposal_id),
    );

    if (!proposal) {
      return notFound("Предложение не найдено");
    }

    if (proposal.status !== "new") {
      return conflict("На это предложение уже ответили");
    }

    const accepted = request.body.accepted === true;
    const answer = String(request.body.answer ?? "").trim();

    if (!accepted && !answer) {
      return badRequest("Объясните автору, почему предложение отклонено");
    }

    const pollId = request.body.poll_id;

    if (pollId != null && !findPoll(Number(pollId))) {
      return notFound("Опрос не найден");
    }

    proposal.status = accepted ? "accepted" : "declined";
    proposal.answer = answer || null;
    proposal.answered_at = new Date().toISOString();
    proposal.poll_id = pollId == null ? null : Number(pollId);

    return ok(item(proposal));
  }),
];
