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
  // подъезд и площадь квартиры знает УК, и у части квартир их нет: на них
  // держатся «Без подъезда» в непроголосовавших и квартиры вне расчёта кворума
  entrance: number | null;
  area: number | null;
  account_no: string;
};

export const ZHILSERVIS: Schemas["OrgContacts"] = {
  id: 1,
  name: "ООО «Жилсервис»",
  phone: "+7 843 200-10-10",
  address: "Казань, ул. Баумана, 10",
  license_no: "16-000123",
  reception_note: "Пн-чт 9:00-18:00, пт до 17:00",
  is_demo: true,
  timezone: "Europe/Moscow",
};

// УК неподключённого дома известна из реестра лицензий, поэтому контакты у неё
// есть, а кабинета в сервисе - нет
export const LENINSKIY: Schemas["OrgContacts"] = {
  id: 2,
  name: "ООО «УК Ленинская»",
  phone: "+7 843 200-40-40",
  address: "Казань, ул. Ленина, 2",
  license_no: "16-000456",
  reception_note: null,
  is_demo: false,
  timezone: "Europe/Moscow",
};

export const HOUSES: MockHouse[] = [
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

export const FLATS: MockFlat[] = [
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
    id: 105,
    house_id: 1,
    number: "12",
    entrance: 1,
    area: 4165,
    account_no: "1600120088",
  },
  {
    id: 106,
    house_id: 1,
    number: "28",
    entrance: 1,
    area: null,
    account_no: "1600280091",
  },
  {
    id: 107,
    house_id: 1,
    number: "63",
    entrance: 3,
    area: 6180,
    account_no: "1600630014",
  },
  {
    id: 108,
    house_id: 1,
    number: "90",
    entrance: 4,
    area: null,
    account_no: "1600900027",
  },
  {
    id: 109,
    house_id: 1,
    number: "101",
    entrance: 4,
    area: 5875,
    account_no: "1601010063",
  },
  {
    id: 110,
    house_id: 1,
    number: "77",
    entrance: 3,
    area: 3240,
    account_no: "1600770049",
  },
  {
    id: 111,
    house_id: 1,
    number: "5",
    entrance: null,
    area: 4100,
    account_no: "1600050072",
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

export const TAKEN_FLAT_IDS = new Set<number>([103]);

export const findHouse = (houseId: number): MockHouse | undefined =>
  HOUSES.find((house) => house.id === houseId);

export const normalize = (value: string): string =>
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

export const flatListItem = (flat: MockFlat): Schemas["FlatListItem"] => ({
  id: flat.id,
  number: flat.number,
  entrance: flat.entrance,
  area: flat.area,
  is_taken: TAKEN_FLAT_IDS.has(flat.id),
});
