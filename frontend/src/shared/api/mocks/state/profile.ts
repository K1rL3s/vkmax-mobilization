import type { components } from "../../schema/generated";

import {
  ZHILSERVIS,
  addressOf,
  findFlat,
  findHouse,
  type MockFlat,
} from "./houses";

type Schemas = components["schemas"];

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

export const user = {
  user_id: 1,
  name: "Тестовый Житель",
  consent_at: null as string | null,
  consent_version: null as string | null,
};

const residencyList: MockResidency[] = [];

const orgs: Schemas["OrgMembership"][] = [
  {
    org_id: 99,
    name: "ООО «Старая управляющая компания»",
    role: "employee",
    is_demo: false,
  },
  {
    org_id: ZHILSERVIS.id,
    name: ZHILSERVIS.name,
    role: "admin",
    is_demo: true,
  },
];

const verifications: MockVerification[] = [];

let nextResidentId = 501;

let nextVerificationId = 9001;

export const acceptConsent = (version: string): void => {
  user.consent_at = new Date().toISOString();
  user.consent_version = version;
};

export const residencies = (): MockResidency[] => residencyList;

export const residencyForHouse = (houseId: number): MockResidency | undefined =>
  residencyList.find((residency) => residency.house_id === houseId);

export const residencyForFlat = (flatId: number): MockResidency | undefined =>
  residencyList.find((residency) => residency.flat_id === flatId);

export const isOrgStaff = (): boolean =>
  orgs.some((org) => org.role !== "executor");

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
    resident_id: nextResidentId++,
    house_id: houseId,
    flat_id: flat?.id ?? null,
    flat_number: flat?.number ?? flatNumber,
    role,
    verified: false,
  };
  residencyList.push(residency);

  return residency;
};

export const activateDemoAccess = () => {
  let org = orgs.find((membership) => membership.org_id === ZHILSERVIS.id);

  if (!org) {
    org = {
      org_id: ZHILSERVIS.id,
      name: ZHILSERVIS.name,
      role: "employee",
      is_demo: true,
    };
    orgs.push(org);
  }

  const flat = findFlat(101)!;
  const residency = addResidency(flat.house_id, flat, null, "tenant");
  residency.flat_id = flat.id;
  residency.flat_number = flat.number;
  residency.verified = true;

  return { org, residency: residencySummary(residency) };
};

export const latestVerification = (
  flatId: number,
): MockVerification | undefined =>
  verifications.findLast((request) => request.flat_id === flatId);

export const addVerification = (
  flatId: number,
  accountNo: string,
  comment: string | null,
  status: Schemas["VerificationStatus"],
  reason: string | null,
): MockVerification => {
  const request: MockVerification = {
    id: nextVerificationId++,
    created_at: new Date().toISOString(),
    flat_id: flatId,
    account_no: accountNo,
    comment,
    status,
    reason,
  };
  verifications.push(request);

  return request;
};

export const setVerified = (residency: MockResidency, flatId: number): void => {
  residency.verified = true;
  residency.flat_id = flatId;
};

export const isChairman = (residency: MockResidency): boolean =>
  residency.house_id === 1 && residency.role === "owner";

export const removeResidency = (residentId: number): boolean => {
  const index = residencyList.findIndex(
    (residency) => residency.resident_id === residentId,
  );

  if (index !== -1) {
    residencyList.splice(index, 1);
  }

  return index !== -1;
};

export function residencySummary(
  residency: MockResidency,
): Schemas["ResidencySummary"] {
  const latest =
    residency.flat_id === null
      ? undefined
      : latestVerification(residency.flat_id);

  return {
    resident_id: residency.resident_id,
    house_id: residency.house_id,
    address: addressOf(residency.house_id),
    role: residency.role,
    status: "active",
    verified: residency.verified,
    is_chairman: isChairman(residency),
    can_see_charges: residency.role === "owner",
    can_vote: residency.role === "owner",
    is_connected: findHouse(residency.house_id)?.is_connected ?? false,
    flat_id: residency.flat_id,
    flat_number: residency.flat_number,
    verification_status: latest?.status ?? null,
    verification_reject_reason:
      latest?.status === "rejected" ? latest.reason : null,
  };
}

export const verificationRequestItem = (
  request: MockVerification,
  flat: MockFlat,
): Schemas["VerificationRequestItem"] => ({
  id: request.id,
  created_at: request.created_at,
  flat_id: flat.id,
  flat_number: flat.number,
  house_id: flat.house_id,
  address: addressOf(flat.house_id),
  user_id: user.user_id,
  user_name: user.name,
  account_no: request.account_no,
  status: request.status,
  comment: request.comment,
  reason: request.reason,
});

export const me = (): Schemas["MeResponse"] => ({
  ...user,
  residencies: residencyList.map(residencySummary),
  orgs,
  is_demo: true,
});
