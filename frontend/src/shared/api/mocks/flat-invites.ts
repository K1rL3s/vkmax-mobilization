import type { components } from "../schema/generated";

import { badRequest, conflict, forbidden, notFound, ok, route } from "./reply";
import {
  addResidency,
  findFlat,
  me,
  residencies,
  residencySummary,
  residencyForHouse,
  setVerified,
} from "./state";

type Schemas = components["schemas"];

type MockInvite = Omit<Schemas["FlatInviteItem"], "deeplink">;

const INVITE_NOT_FOUND = "Приглашение не найдено";

const hours = (count: number) =>
  new Date(Date.now() + count * 60 * 60 * 1000).toISOString();

// соседи мок-пользователя: в state.ts живёт только он сам, а секции жителей
// нужен арендатор, вошедший по коду
const NEIGHBOURS: Record<number, Schemas["FlatResidentItem"][]> = {
  101: [
    {
      resident_id: 9101,
      user_id: 71,
      name: "Анна Смирнова",
      role: "tenant",
      status: "active",
      verified: true,
      is_chairman: false,
      can_see_charges: false,
      can_vote: false,
    },
  ],
  104: [
    {
      resident_id: 9104,
      user_id: 73,
      name: "Ильдар Хасанов",
      role: "owner",
      status: "active",
      verified: true,
      is_chairman: false,
      can_see_charges: true,
      can_vote: true,
    },
  ],
  105: [
    {
      resident_id: 9105,
      user_id: 72,
      name: "Анна Смирнова",
      role: "tenant",
      status: "active",
      verified: true,
      is_chairman: false,
      can_see_charges: false,
      can_vote: false,
    },
  ],
};

// у квартир 101 и 105 по одному живому коду, отозванный и истёкший в списке
// не показываются; код квартиры 104 из дома 2 - для проверки активации
const seedInvites = (): MockInvite[] =>
  [101, 105].flatMap((flatId) => [
    {
      code: `K7M-4PX${flatId}`,
      flat_id: flatId,
      created_at: hours(-24),
      expires_at: hours(48),
      max_activations: 2,
      activations_used: 1,
      revoked_at: null,
    },
    {
      code: `OLD-REV${flatId}`,
      flat_id: flatId,
      created_at: hours(-96),
      expires_at: hours(24),
      max_activations: 1,
      activations_used: 0,
      revoked_at: hours(-90),
    },
    {
      code: `OLD-EXP${flatId}`,
      flat_id: flatId,
      created_at: hours(-200),
      expires_at: hours(-128),
      max_activations: 1,
      activations_used: 0,
      revoked_at: null,
    },
  ]);

let invites: MockInvite[] = [
  ...seedInvites(),
  {
    code: "TENANT-104",
    flat_id: 104,
    created_at: hours(-1),
    expires_at: hours(72),
    max_activations: 5,
    activations_used: 0,
    revoked_at: null,
  },
];

const item = (invite: MockInvite): Schemas["FlatInviteItem"] => ({
  ...invite,
  deeplink: `https://max.ru/zheka_bot?start=flat_${invite.code}`,
});

const isLive = (invite: MockInvite) =>
  invite.revoked_at === null && new Date(invite.expires_at) > new Date();

const residentOfFlat = (flatId: number) =>
  residencies().find((residency) => residency.flat_id === flatId);

const positive = (value: unknown, fallback: number): number | null => {
  const parsed = value === undefined ? fallback : Number(value);

  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
};

export const flatInvitesConfigs = [
  {
    path: "/flats/:flat_id/residents" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const flatId = Number(request.params.flat_id);
        const residency = residentOfFlat(flatId);

        if (!findFlat(flatId)) {
          return notFound("Квартира не найдена");
        }

        if (!residency) {
          return forbidden("Вы не житель этой квартиры");
        }

        const summary = residencySummary(residency);
        const self: Schemas["FlatResidentItem"] = {
          resident_id: summary.resident_id,
          user_id: me().user_id,
          name: me().name,
          role: summary.role,
          status: summary.status,
          verified: summary.verified,
          is_chairman: summary.is_chairman,
          can_see_charges: summary.can_see_charges,
          can_vote: summary.can_vote,
        };

        return ok([self, ...(NEIGHBOURS[flatId] ?? [])]);
      }),
    ],
  },
  {
    path: "/flats/:flat_id/invites" as const,
    method: "get" as const,
    routes: [
      route((request) => {
        const flatId = Number(request.params.flat_id);

        if (!residentOfFlat(flatId)) {
          return forbidden("Вы не житель этой квартиры");
        }

        return ok(
          invites
            .filter((invite) => invite.flat_id === flatId)
            .sort((a, b) => b.created_at.localeCompare(a.created_at))
            .map(item),
        );
      }),
    ],
  },
  {
    path: "/flats/:flat_id/invites" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const flatId = Number(request.params.flat_id);
        const expiresIn = positive(request.body.expires_in_hours, 72);
        const maxActivations = positive(request.body.max_activations, 1);

        if (expiresIn === null) {
          return badRequest("Срок жизни кода - больше нуля часов");
        }

        if (maxActivations === null) {
          return badRequest("Число активаций - больше нуля");
        }

        const residency = residentOfFlat(flatId);

        if (!residency) {
          return forbidden("Вы не житель этой квартиры");
        }

        if (residency.role !== "owner") {
          return forbidden(
            "Код приглашения выдает собственник, а не арендатор",
          );
        }

        if (!residency.verified) {
          return forbidden("Сначала подтвердите квартиру");
        }

        const invite: MockInvite = {
          code: Math.random().toString(36).slice(2, 13),
          flat_id: flatId,
          created_at: new Date().toISOString(),
          expires_at: hours(expiresIn),
          max_activations: maxActivations,
          activations_used: 0,
          revoked_at: null,
        };
        invites = [...invites, invite];

        return ok(item(invite));
      }),
    ],
  },
  {
    path: "/flat-invites/:code" as const,
    method: "delete" as const,
    routes: [
      route((request) => {
        const invite = invites.find(
          (candidate) => candidate.code === request.params.code,
        );
        const residency = invite && residentOfFlat(invite.flat_id);

        if (!invite || residency?.role !== "owner" || !residency.verified) {
          return notFound(INVITE_NOT_FOUND);
        }

        invite.revoked_at ??= new Date().toISOString();

        return ok({ ok: true });
      }),
    ],
  },
  {
    path: "/flat-invites/:code/activate" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const invite = invites.find(
          (candidate) => candidate.code === request.params.code,
        );
        const flat = invite && findFlat(invite.flat_id);

        if (!invite || !flat) {
          return notFound(INVITE_NOT_FOUND);
        }

        const existing = residencyForHouse(flat.house_id);

        if (existing?.flat_id === flat.id) {
          return isLive(invite)
            ? ok(residencySummary(existing))
            : conflict("Код приглашения истек или отозван");
        }

        if (existing?.flat_id != null) {
          return conflict(
            "Житель привязан к другой квартире, переезд оформляет УК",
          );
        }

        if (
          !isLive(invite) ||
          invite.activations_used >= invite.max_activations
        ) {
          return conflict("Код приглашения истек, отозван или исчерпан");
        }

        invite.activations_used += 1;
        const residency = addResidency(flat.house_id, flat, null, "tenant");
        setVerified(residency, flat.id);

        return ok(residencySummary(residency));
      }),
    ],
  },
];
