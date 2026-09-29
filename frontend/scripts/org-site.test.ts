import assert from "node:assert/strict";
import { test } from "node:test";

const constraintsUrl = new URL(
  "../src/features/admin-org/domain/org-form-constraints.ts",
  import.meta.url,
).href;

const { isSiteAddress } = (await import(constraintsUrl)) as {
  isSiteAddress: (value: string) => boolean;
};

test("takes the addresses the server takes", () => {
  for (const site of [
    "uk-primer.ru",
    "https://www.uk.ru/docs",
    "HTTP://UK.RU",
    "уккомфорт.рф",
    "https://жкх-сервис.рф/контакты",
    "uk.ru?page=1",
    "uk.ru#contacts",
  ]) {
    assert.equal(isSiteAddress(site), true, site);
  }
});

test("refuses what is not a site", () => {
  for (const site of [
    "не знаю",
    "javascript:alert(1)",
    "uk",
    "uk.ru:8080",
    "user@uk.ru",
    "//uk.ru",
  ]) {
    assert.equal(isSiteAddress(site), false, site);
  }
});
