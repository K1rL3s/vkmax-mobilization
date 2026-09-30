import type { components } from "../../schema/generated";

type Schemas = components["schemas"];

export type MockHouse = {
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

export type MockFlat = {
  id: number;
  house_id: number;
  number: string;
  entrance: number | null;
  area: number | null;
  account_no: string;
};

export const ZHILSERVIS: Schemas["OrgContacts"] = {
  id: 1,
  name: "Демо-УК «Надежный дом»",
  phone: "+7 (000) 000-00-03",
  address: "Адрес вымышлен, организация создана для демо",
  email: "priem-3@demo-uk.example.com",
  site: "https://demo-uk-3.example.com",
  license_no: null,
  reception_note: "Пн-чт 9:00-18:00, пт до 17:00",
  emergency_phone: "+7 (000) 000-01-03",
  is_demo: true,
  timezone: "Europe/Moscow",
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
    org: {
      id: 2,
      name: "ООО «УК Ленинская»",
      phone: "+7 843 200-40-40",
      address: "Казань, ул. Ленина, 2",
      email: "info@uk-leninskaya.ru",
      site: null,
      license_no: "16-000456",
      reception_note: null,
      is_demo: false,
      timezone: "Europe/Moscow",
    },
  },
];

const flat = (
  id: number,
  number: string,
  entrance: number | null,
  area: number | null,
  house_id = 1,
): MockFlat => ({
  id,
  house_id,
  number,
  entrance,
  area,
  account_no: number.padStart(10, "0"),
});

export const FLATS: MockFlat[] = [
  flat(101, "45", 2, 5420),
  flat(102, "112", 4, 7310),
  flat(103, "7", 1, 3890),
  flat(105, "12", 1, 4165),
  flat(106, "28", 1, null),
  flat(107, "63", 3, 6180),
  flat(108, "90", 4, null),
  flat(109, "101", 4, 5875),
  flat(110, "77", 3, 3240),
  flat(111, "5", null, 4100),
  flat(104, "3", 1, 4210, 2),
];

export const findHouse = (houseId: number): MockHouse | undefined =>
  HOUSES.find((house) => house.id === houseId);

export const orgOf = (houseId: number): number | null =>
  findHouse(houseId)?.org?.id ?? null;

const normalize = (value: string): string =>
  value.trim().toLowerCase().replace(/\s+/g, " ");

export const searchHouses = (query: string): MockHouse[] => {
  const words = normalize(query).split(" ").filter(Boolean);

  return words.length === 0
    ? []
    : HOUSES.filter((house) => {
        const address = normalize(
          `${house.city} ${house.street} ${house.building}`,
        );

        return words.every((word) => address.includes(word));
      });
};

export const houseFlats = (houseId: number, query: string): MockFlat[] => {
  const normalized = normalize(query);
  const flats = FLATS.filter((flat) => flat.house_id === houseId);

  return normalized
    ? flats.filter((flat) => flat.number.toLowerCase() === normalized)
    : flats;
};

export const findFlat = (flatId: number): MockFlat | undefined =>
  FLATS.find((flat) => flat.id === flatId);

export const address = (house: MockHouse): string =>
  `${house.city}, ул. ${house.street}, д. ${house.building}`;

export const addressOf = (houseId: number): string => {
  const house = findHouse(houseId);

  return house ? address(house) : "";
};

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

export const flatListItem = (flat: MockFlat): Schemas["FlatListItem"] => ({
  id: flat.id,
  number: flat.number,
  entrance: flat.entrance,
  area: flat.area,
  is_taken: flat.id === 103,
});

const demand = new Map<number, number>([[4, 11]]);

const demandSent = new Set<number>();

export const signalDemand = (houseId: number): void => {
  if (!demandSent.has(houseId)) {
    demand.set(houseId, demandTotal(houseId) + 1);
    demandSent.add(houseId);
  }
};

export const isDemandSent = (houseId: number): boolean =>
  demandSent.has(houseId);

export const demandTotal = (houseId: number): number =>
  demand.get(houseId) ?? 0;

export const orgHouses = (orgId: number): MockHouse[] =>
  HOUSES.filter((house) => house.org?.id === orgId);
