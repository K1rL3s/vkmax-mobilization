// Моки до появления поиска домов в API (shared/api/schema/main.yaml пока пустой).

export type House = {
  id: string;
  street: string;
  number: string;
  city: string;
};

export const HOUSES_MOCK: House[] = [
  {
    id: "1",
    street: "Баумана",
    number: "12",
    city: "Казань, Республика Татарстан",
  },
  {
    id: "2",
    street: "Баумана",
    number: "14",
    city: "Казань, Республика Татарстан",
  },
  {
    id: "3",
    street: "Баумана",
    number: "16",
    city: "Казань, Республика Татарстан",
  },
  {
    id: "4",
    street: "Ленина",
    number: "12",
    city: "Казань, Республика Татарстан",
  },
  {
    id: "5",
    street: "Пушкина",
    number: "3",
    city: "Казань, Республика Татарстан",
  },
];

export const searchHouses = (query: string) => {
  const normalized = query.trim().toLowerCase();

  if (!normalized) {
    return [];
  }

  return HOUSES_MOCK.filter((house) =>
    house.street.toLowerCase().includes(normalized),
  );
};

export const formatHouseAddress = (house: House) =>
  `ул. ${house.street}, ${house.number}`;
