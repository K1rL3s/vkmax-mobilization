import type { components } from "../schema/generated";

import { endpoint, forbidden, ok } from "./reply";
import { hours, isChairman, residencyForHouse } from "./state";

type MockHandover = components["schemas"]["ChairmanHandoverItem"];

const handovers = new Map<number, MockHandover>();

const NOT_A_CHAIRMAN =
  "Передать роль может только действующий председатель совета дома";

const isLive = (handover: MockHandover) =>
  new Date(handover.expires_at) > new Date();

const actingChairman = (houseId: number) => {
  const residency = residencyForHouse(houseId);

  return residency !== undefined && isChairman(residency);
};

export const chairmanHandoverConfigs = [
  endpoint("get", "/houses/:house_id/chairman-handover", (request) => {
    const houseId = Number(request.params.house_id);

    if (!actingChairman(houseId)) {
      return forbidden(NOT_A_CHAIRMAN);
    }

    const found = handovers.get(houseId);

    return ok(found && isLive(found) ? found : null);
  }),
  endpoint("post", "/houses/:house_id/chairman-handover", (request) => {
    const houseId = Number(request.params.house_id);

    if (!actingChairman(houseId)) {
      return forbidden(NOT_A_CHAIRMAN);
    }

    const code = Math.random().toString(36).slice(2, 13);
    const created: MockHandover = {
      code,
      house_id: houseId,
      created_at: new Date().toISOString(),
      expires_at: hours(48),
      deeplink: `https://max.ru/zheka_bot?start=chair_${code}`,
    };
    handovers.set(houseId, created);

    return ok(created);
  }),
  endpoint("delete", "/houses/:house_id/chairman-handover", (request) => {
    const houseId = Number(request.params.house_id);

    if (!actingChairman(houseId)) {
      return forbidden(NOT_A_CHAIRMAN);
    }

    handovers.delete(houseId);

    return ok({ ok: true });
  }),
];
