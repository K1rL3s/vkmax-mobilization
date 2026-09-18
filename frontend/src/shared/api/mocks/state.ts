import type { components } from "../schema/generated";

type Schemas = components["schemas"];

export type MockRequest = {
  params: Record<string, string>;
  query: Record<string, string | undefined>;
  body: Record<string, unknown>;
  headers: Record<string, string | undefined>;
};

type MockHouse = {
  id: number;
  region: string;
  city: string;
  street: string;
  building: string;
  is_connected: boolean;
  entrances: number;
  cadastral_no: string;
  built_year: number;
  floors: number;
  area: number;
  lat: number;
  lon: number;
  org: Schemas["OrgContacts"] | null;
};

type MockFlat = {
  id: number;
  house_id: number;
  number: string;
  entrance: number;
  area: number;
  account_no: string;
};

type MockVerification = {
  id: number;
  created_at: string;
  flat_id: number;
  account_no: string;
  comment: string | null;
  status: Schemas["VerificationStatus"];
  reason: string | null;
};

type MockResidency = {
  resident_id: number;
  house_id: number;
  flat_id: number | null;
  flat_number: string | null;
  role: Schemas["ResidentRole"];
  verified: boolean;
};

const ZHILSERVIS: Schemas["OrgContacts"] = {
  id: 1,
  name: "ООО «Жилсервис»",
  phone: "+7 843 200-10-10",
  address: "Казань, ул. Баумана, 10",
  license_no: "16-000123",
  reception_note: "Пн-чт 9:00-18:00, пт до 17:00",
  is_demo: true,
};

// УК неподключённого дома известна из реестра лицензий, поэтому контакты у неё
// есть, а кабинета в сервисе - нет
const LENINSKIY: Schemas["OrgContacts"] = {
  id: 2,
  name: "ООО «УК Ленинская»",
  phone: "+7 843 200-40-40",
  address: "Казань, ул. Ленина, 2",
  license_no: "16-000456",
  reception_note: null,
  is_demo: false,
};

const HOUSES: MockHouse[] = [
  {
    id: 1,
    region: "Республика Татарстан",
    city: "Казань",
    street: "Баумана",
    building: "12",
    is_connected: true,
    entrances: 4,
    cadastral_no: "16:50:011725:128",
    built_year: 1987,
    floors: 9,
    area: 845012,
    lat: 55.7903,
    lon: 49.1221,
    org: ZHILSERVIS,
  },
  {
    id: 2,
    region: "Республика Татарстан",
    city: "Казань",
    street: "Баумана",
    building: "14",
    is_connected: true,
    entrances: 2,
    cadastral_no: "16:50:011725:131",
    built_year: 1992,
    floors: 5,
    area: 412300,
    lat: 55.7911,
    lon: 49.1229,
    org: ZHILSERVIS,
  },
  {
    id: 3,
    region: "Республика Татарстан",
    city: "Казань",
    street: "Баумана",
    building: "16",
    is_connected: true,
    entrances: 3,
    cadastral_no: "16:50:011725:140",
    built_year: 2004,
    floors: 12,
    area: 690455,
    lat: 55.7918,
    lon: 49.1235,
    org: ZHILSERVIS,
  },
  {
    id: 4,
    region: "Республика Татарстан",
    city: "Казань",
    street: "Ленина",
    building: "4",
    is_connected: false,
    entrances: 2,
    cadastral_no: "16:50:011802:44",
    built_year: 1975,
    floors: 5,
    area: 310800,
    lat: 55.7841,
    lon: 49.1103,
    org: LENINSKIY,
  },
];

const FLATS: MockFlat[] = [
  {
    id: 101,
    house_id: 1,
    number: "45",
    entrance: 2,
    area: 5420,
    account_no: "1600450012",
  },
  {
    id: 102,
    house_id: 1,
    number: "112",
    entrance: 4,
    area: 7310,
    account_no: "1601120034",
  },
  {
    id: 103,
    house_id: 1,
    number: "7",
    entrance: 1,
    area: 3890,
    account_no: "1600070055",
  },
  {
    id: 104,
    house_id: 2,
    number: "3",
    entrance: 1,
    area: 4210,
    account_no: "1400030077",
  },
];

const TAKEN_FLAT_IDS = new Set<number>([103]);

const state = {
  user: {
    user_id: 1,
    name: "Тестовый Житель",
    consent_at: null as string | null,
    consent_version: null as string | null,
  },
  residencies: [] as MockResidency[],
  verifications: [] as MockVerification[],
  demand: new Map<number, number>([[4, 11]]),
  demandSent: new Set<number>(),
  nextResidentId: 501,
  nextVerificationId: 9001,
};

export const resetState = (): void => {
  state.user.consent_at = null;
  state.user.consent_version = null;
  state.residencies = [];
  state.verifications = [];
  state.demand = new Map([[4, 11]]);
  state.demandSent = new Set();
  state.nextResidentId = 501;
  state.nextVerificationId = 9001;
};

export const hasConsent = (): boolean => state.user.consent_at !== null;

export const acceptConsent = (version: string): void => {
  state.user.consent_at = new Date().toISOString();
  state.user.consent_version = version;
};

export const findHouse = (houseId: number): MockHouse | undefined =>
  HOUSES.find((house) => house.id === houseId);

const normalize = (value: string): string =>
  value.trim().toLowerCase().replace(/\s+/g, " ");

export const searchHouses = (query: string): MockHouse[] => {
  const words = normalize(query).split(" ").filter(Boolean);

  if (words.length === 0) {
    return [];
  }

  return HOUSES.filter((house) => {
    const address = normalize(
      `${house.city} ${house.street} ${house.building}`,
    );

    return words.every((word) => address.includes(word));
  });
};

export const houseFlats = (houseId: number, query: string): MockFlat[] => {
  const normalized = normalize(query);
  const flats = FLATS.filter((flat) => flat.house_id === houseId);

  if (!normalized) {
    return flats;
  }

  return flats.filter((flat) => flat.number.toLowerCase() === normalized);
};

export const findFlat = (flatId: number): MockFlat | undefined =>
  FLATS.find((flat) => flat.id === flatId);

export const residencies = (): MockResidency[] => state.residencies;

export const residencyForHouse = (houseId: number): MockResidency | undefined =>
  state.residencies.find((residency) => residency.house_id === houseId);

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

export const signalDemand = (houseId: number): number => {
  if (state.demandSent.has(houseId)) {
    return demandTotal(houseId);
  }

  const total = (state.demand.get(houseId) ?? 0) + 1;
  state.demand.set(houseId, total);
  state.demandSent.add(houseId);

  return total;
};

export const demandTotal = (houseId: number): number =>
  state.demand.get(houseId) ?? 0;

export const address = (house: MockHouse): string =>
  `${house.city}, ул. ${house.street}, д. ${house.building}`;

export const houseListItem = (house: MockHouse): Schemas["HouseListItem"] => ({
  id: house.id,
  address: address(house),
  city: `${house.city}, ${house.region}`,
  street: house.street,
  building: house.building,
  is_connected: house.is_connected,
  org_name: house.org?.name ?? null,
  distance_m: null,
});

export const houseCard = (house: MockHouse): Schemas["HouseCard"] => ({
  id: house.id,
  address: address(house),
  region: house.region,
  city: house.city,
  street: house.street,
  building: house.building,
  cadastral_no: house.cadastral_no,
  entrances: house.entrances,
  is_connected: house.is_connected,
  demand_count: demandTotal(house.id),
  demand_sent: state.demandSent.has(house.id),
  built_year: house.built_year,
  floors: house.floors,
  area: house.area,
  lat: house.lat,
  lon: house.lon,
  org: house.org,
  my_residency: (() => {
    const residency = residencyForHouse(house.id);

    return residency ? residencySummary(residency) : null;
  })(),
  chat_binding_code: null,
  chat_bound: false,
  overhaul: null,
  documents: [],
});

export const flatListItem = (flat: MockFlat): Schemas["FlatListItem"] => ({
  id: flat.id,
  number: flat.number,
  entrance: flat.entrance,
  area: flat.area,
  is_taken: TAKEN_FLAT_IDS.has(flat.id),
});

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
    is_chairman: false,
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
  orgs: [],
  is_demo: true,
});
