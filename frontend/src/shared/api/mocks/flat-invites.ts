import type { components } from "../schema/generated";

import {
  badRequest,
  conflict,
  endpoint,
  forbidden,
  notFound,
  ok,
} from "./reply";
import {
  addResidency,
  findFlat,
  hours,
  residencyForFlat,
  residencySummary,
  residencyForHouse,
  setVerified,
  user,
} from "./state";

type Schemas = components["schemas"];

type MockInvite = Omit<Schemas["FlatInviteItem"], "deeplink">;

const neighbour = (
  resident_id: number,
  user_id: number,
  name: string,
  role: Schemas["ResidentRole"],
): Schemas["FlatResidentItem"] => ({
  resident_id,
  user_id,
  name,
  role,
  status: "active",
  verified: true,
  is_chairman: false,
  can_see_charges: role === "owner",
  can_vote: role === "owner",
});

const NEIGHBOURS: Record<number, Schemas["FlatResidentItem"][]> = {
  101: [neighbour(9101, 71, "Анна Смирнова", "tenant")],
  104: [neighbour(9104, 73, "Ильдар Хасанов", "owner")],
  105: [neighbour(9105, 72, "Анна Смирнова", "tenant")],
};

const makeInvite = (
  code: string,
  flat_id: number,
  created_at: string,
  expires_at: string,
  max_activations: number,
  activations_used = 0,
  revoked_at: string | null = null,
): MockInvite => ({
  code,
  flat_id,
  created_at,
  expires_at,
  max_activations,
  activations_used,
  revoked_at,
});

const invites: MockInvite[] = [
  ...[101, 105].flatMap((flatId) => [
    makeInvite(`K7M-4PX${flatId}`, flatId, hours(-24), hours(48), 2, 1),
    makeInvite(
      `OLD-REV${flatId}`,
      flatId,
      hours(-96),
      hours(24),
      1,
      0,
      hours(-90),
    ),
    makeInvite(`OLD-EXP${flatId}`, flatId, hours(-200), hours(-128), 1),
  ]),
  makeInvite("TENANT-104", 104, hours(-1), hours(72), 5),
];

const item = (invite: MockInvite): Schemas["FlatInviteItem"] => ({
  ...invite,
  deeplink: `https://max.ru/zheka_bot?start=flat_${invite.code}`,
});

const isLive = (invite: MockInvite) =>
  invite.revoked_at === null && new Date(invite.expires_at) > new Date();

const positive = (value: unknown, fallback: number): number | null => {
  const parsed = value === undefined ? fallback : Number(value);

  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
};

export const flatInvitesConfigs = [
  endpoint("get", "/flats/:flat_id/residents", (request) => {
    const flatId = Number(request.params.flat_id);
    const residency = residencyForFlat(flatId);

    if (!findFlat(flatId)) {
      return notFound("Квартира не найдена");
    }

    if (!residency) {
      return forbidden("Вы не житель этой квартиры");
    }

    const summary = residencySummary(residency);

    return ok([
      {
        resident_id: summary.resident_id,
        user_id: user.user_id,
        name: user.name,
        role: summary.role,
        status: summary.status,
        verified: summary.verified,
        is_chairman: summary.is_chairman,
        can_see_charges: summary.can_see_charges,
        can_vote: summary.can_vote,
      } satisfies Schemas["FlatResidentItem"],
      ...(NEIGHBOURS[flatId] ?? []),
    ]);
  }),
  endpoint("get", "/flats/:flat_id/invites", (request) => {
    const flatId = Number(request.params.flat_id);

    return residencyForFlat(flatId)
      ? ok(
          invites
            .filter((invite) => invite.flat_id === flatId)
            .sort((a, b) => b.created_at.localeCompare(a.created_at))
            .map(item),
        )
      : forbidden("Вы не житель этой квартиры");
  }),
  endpoint("post", "/flats/:flat_id/invites", (request) => {
    const flatId = Number(request.params.flat_id);
    const expiresIn = positive(request.body.expires_in_hours, 72);
    const maxActivations = positive(request.body.max_activations, 1);

    if (expiresIn === null) {
      return badRequest("Срок жизни кода - больше нуля часов");
    }

    if (maxActivations === null) {
      return badRequest("Число активаций - больше нуля");
    }

    const residency = residencyForFlat(flatId);

    if (!residency) {
      return forbidden("Вы не житель этой квартиры");
    }

    if (residency.role !== "owner") {
      return forbidden("Код приглашения выдает собственник, а не арендатор");
    }

    if (!residency.verified) {
      return forbidden("Сначала подтвердите квартиру");
    }

    const created = makeInvite(
      Math.random().toString(36).slice(2, 13),
      flatId,
      new Date().toISOString(),
      hours(expiresIn),
      maxActivations,
    );
    invites.push(created);

    return ok(item(created));
  }),
  endpoint("delete", "/flat-invites/:code", (request) => {
    const found = invites.find(({ code }) => code === request.params.code);
    const residency = found && residencyForFlat(found.flat_id);

    if (!found || residency?.role !== "owner" || !residency.verified) {
      return notFound("Приглашение не найдено");
    }

    found.revoked_at ??= new Date().toISOString();

    return ok({ ok: true });
  }),
  endpoint("post", "/flat-invites/:code/activate", (request) => {
    const found = invites.find(({ code }) => code === request.params.code);
    const flat = found && findFlat(found.flat_id);

    if (!found || !flat) {
      return notFound("Приглашение не найдено");
    }

    const existing = residencyForHouse(flat.house_id);

    if (existing?.flat_id === flat.id) {
      return isLive(found)
        ? ok(residencySummary(existing))
        : conflict("Код приглашения истек или отозван");
    }

    if (existing?.flat_id != null) {
      return conflict(
        "Житель привязан к другой квартире, переезд оформляет УК",
      );
    }

    if (!isLive(found) || found.activations_used >= found.max_activations) {
      return conflict("Код приглашения истек, отозван или исчерпан");
    }

    found.activations_used += 1;
    const residency = addResidency(flat.house_id, flat, null, "tenant");
    setVerified(residency, flat.id);

    return ok(residencySummary(residency));
  }),
];
