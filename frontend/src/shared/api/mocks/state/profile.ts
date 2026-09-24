import type { components } from "../../schema/generated";

type Schemas = components["schemas"];

import {
  ZHILSERVIS,
  address,
  findFlat,
  findHouse,
  type MockFlat,
} from "./houses";

export type MockVerification = {
  id: number;
  created_at: string;
  flat_id: number;
  account_no: string;
  comment: string | null;
  status: Schemas["VerificationStatus"];
  reason: string | null;
};

export type MockResidency = {
  resident_id: number;
  house_id: number;
  flat_id: number | null;
  flat_number: string | null;
  role: Schemas["ResidentRole"];
  verified: boolean;
};

export const SEED_ORGS: Schemas["OrgMembership"][] = [
  {
    org_id: 99,
    name: "ООО «Старая управляющая компания»",
    role: "employee",
    is_demo: false,
  },
  // «Жилсервис» - организация посеянных домов, заявок и часов приёма, и
  // мок-пользователь в ней администратор: иначе часы приёма заперты ролью и
  // сквозной сценарий «УК правит часы - житель видит другие слоты» локально
  // не проходится. Случай сотрудника без прав проверяется правкой этой роли
  {
    org_id: ZHILSERVIS.id,
    name: ZHILSERVIS.name,
    role: "admin",
    is_demo: true,
  },
];

const state = {
  user: {
    user_id: 1,
    name: "Тестовый Житель",
    consent_at: null as string | null,
    consent_version: null as string | null,
  },
  residencies: [] as MockResidency[],
  // сотрудник УК часто живёт в доме своей же организации - мок-пользователь
  // держит обе роли, иначе кабинет УК локально не открыть
  orgs: [...SEED_ORGS],
  verifications: [] as MockVerification[],
  nextResidentId: 501,
  nextVerificationId: 9001,
};

export const resetProfile = (): void => {
  state.user.consent_at = null;
  state.user.consent_version = null;
  state.residencies = [];
  state.orgs = [...SEED_ORGS];
  state.verifications = [];
  state.nextResidentId = 501;
  state.nextVerificationId = 9001;
};

export const hasConsent = (): boolean => state.user.consent_at !== null;

export const acceptConsent = (version: string): void => {
  state.user.consent_at = new Date().toISOString();
  state.user.consent_version = version;
};

export const residencies = (): MockResidency[] => state.residencies;

export const residencyForHouse = (houseId: number): MockResidency | undefined =>
  state.residencies.find((residency) => residency.house_id === houseId);

export const isOrgStaff = (): boolean =>
  state.orgs.some((org) => org.role !== "executor");

export const addResidency = (
  houseId: number,
  flat: MockFlat | null,
  flatNumber: string | null,
  role: Schemas["ResidentRole"],
): MockResidency => {
  const existing = residencyForHouse(houseId);

  if (existing) {
    return existing;
  }

  const residency: MockResidency = {
    resident_id: state.nextResidentId,
    house_id: houseId,
    flat_id: flat?.id ?? null,
    flat_number: flat?.number ?? flatNumber,
    role,
    verified: false,
  };
  state.nextResidentId += 1;
  state.residencies.push(residency);

  return residency;
};

export const activateFlatResidency = (flat: MockFlat): MockResidency => {
  const residency = addResidency(flat.house_id, flat, null, "tenant");
  residency.flat_id = flat.id;
  residency.flat_number = flat.number;
  residency.verified = true;

  return residency;
};

export const activateDemoAccess = (): {
  org: Schemas["OrgMembership"];
  residency: MockResidency;
} => {
  let org = state.orgs.find(
    (membership) => membership.org_id === ZHILSERVIS.id,
  );

  if (!org) {
    org = {
      org_id: ZHILSERVIS.id,
      name: ZHILSERVIS.name,
      role: "employee",
      is_demo: true,
    };
    state.orgs.push(org);
  }

  const flat = findFlat(101);

  if (!flat) {
    throw new Error("В demo mock отсутствует квартира");
  }

  return { org, residency: activateFlatResidency(flat) };
};

export const latestVerification = (
  flatId: number,
): MockVerification | undefined =>
  state.verifications.findLast((request) => request.flat_id === flatId);

export const addVerification = (
  flatId: number,
  accountNo: string,
  comment: string | null,
  status: Schemas["VerificationStatus"],
  reason: string | null,
): MockVerification => {
  const request: MockVerification = {
    id: state.nextVerificationId,
    created_at: new Date().toISOString(),
    flat_id: flatId,
    account_no: accountNo,
    comment,
    status,
    reason,
  };
  state.nextVerificationId += 1;
  state.verifications.push(request);

  return request;
};

// подтверждение и есть тот момент, когда у привязки появляется квартира:
// до него житель мог указать ее свободным номером
export const setVerified = (residency: MockResidency, flatId: number): void => {
  residency.verified = true;
  residency.flat_id = flatId;
};

// житель демо-данных - председатель совета дома 1: там же лежат опросы,
// которые он завёл, и без этого создание опроса нечем проверить
export const isChairman = (residency: MockResidency): boolean =>
  residency.house_id === 1 && residency.role === "owner";

export const removeResidency = (residentId: number): boolean => {
  const next = state.residencies.filter(
    (residency) => residency.resident_id !== residentId,
  );

  if (next.length === state.residencies.length) {
    return false;
  }

  state.residencies = next;

  return true;
};

export function residencySummary(
  residency: MockResidency,
): Schemas["ResidencySummary"] {
  const house = findHouse(residency.house_id);
  const latest =
    residency.flat_id === null
      ? undefined
      : latestVerification(residency.flat_id);

  return {
    resident_id: residency.resident_id,
    house_id: residency.house_id,
    address: house ? address(house) : "",
    role: residency.role,
    status: "active",
    verified: residency.verified,
    is_chairman: isChairman(residency),
    can_see_charges: residency.role === "owner",
    can_vote: residency.role === "owner",
    is_connected: house?.is_connected ?? false,
    flat_id: residency.flat_id,
    flat_number: residency.flat_number,
    verification_status: latest?.status ?? null,
    // причина принадлежит отказу: у одобренного запроса в этом поле заметка УК
    verification_reject_reason:
      latest?.status === "rejected" ? latest.reason : null,
  };
}

export const verificationRequestItem = (
  request: MockVerification,
  flat: MockFlat,
): Schemas["VerificationRequestItem"] => {
  const house = findHouse(flat.house_id);

  return {
    id: request.id,
    created_at: request.created_at,
    flat_id: flat.id,
    flat_number: flat.number,
    house_id: flat.house_id,
    address: house ? address(house) : "",
    user_id: state.user.user_id,
    user_name: state.user.name,
    account_no: request.account_no,
    status: request.status,
    comment: request.comment,
    reason: request.reason,
  };
};

export const me = (): Schemas["MeResponse"] => ({
  user_id: state.user.user_id,
  name: state.user.name,
  consent_at: state.user.consent_at,
  consent_version: state.user.consent_version,
  residencies: state.residencies.map(residencySummary),
  orgs: state.orgs,
  is_demo: true,
});
