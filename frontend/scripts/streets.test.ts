import assert from "node:assert/strict";
import { test } from "node:test";

type House = { id: number; city: string; street: string; address: string };

const { groupHousesByStreet } = (await import(
  new URL(
    "../src/features/admin-announcements/domain/streets.ts",
    import.meta.url,
  ).href
)) as {
  groupHousesByStreet: (
    houses: House[],
  ) => { street: string; houses: House[] }[];
};

const house = (id: number, city: string, street: string, building: string) => ({
  id,
  city,
  street,
  address: `${city}, ${street}, ${building}`,
});

test("a building with a comma stays on its street", () => {
  const groups = groupHousesByStreet([
    house(1, "Казань", "Большая Красная улица", "58, лит. Б"),
    house(2, "Казань", "Большая Красная улица", "58, лит. Д"),
    house(3, "Казань", "Большая Красная улица", "60"),
    house(4, "Казань", "улица Жуковского", "17, лит. А"),
  ]);

  assert.deepEqual(
    groups.map(({ street, houses }) => [street, houses.map(({ id }) => id)]),
    [
      ["Казань, Большая Красная улица", [1, 2, 3]],
      ["Казань, улица Жуковского", [4]],
    ],
  );
});

test("one street name in two cities makes two groups", () => {
  const groups = groupHousesByStreet([
    house(1, "Москва", "Ленинский проспект", "3"),
    house(2, "Санкт-Петербург", "Ленинский проспект", "54"),
  ]);

  assert.equal(groups.length, 2);
});
