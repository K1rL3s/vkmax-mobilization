import assert from "node:assert/strict";
import { test } from "node:test";

process.env.TZ = "Europe/Moscow";

const lettersUrl = new URL(
  "../src/features/request/domain/letters.ts",
  import.meta.url,
).href;

const { leakActLetter, recalcLetter, requestLetter } = (await import(
  lettersUrl
)) as {
  leakActLetter: (...args: unknown[]) => string;
  recalcLetter: (...args: unknown[]) => string;
  requestLetter: (...args: unknown[]) => { title: string } | null;
};

const org = {
  id: 1,
  name: "ООО «УК Уютный дом»",
  phone: "+7 000 000-00-01",
  address: "г. Казань, ул. Баумана, д. 1",
  license_no: "016-000123",
};

const house = {
  id: 7,
  address: "г. Казань, ул. Пушкина, д. 10",
  region: "Республика Татарстан",
  org,
};

const request = {
  id: 142,
  created_at: "2026-09-28T11:10:00Z",
  category: "leak",
  category_label: "Протечка",
  description: "Течет с потолка в ванной",
  status: "new",
  flat_number: "12",
  timeline: [],
};

const heating = {
  ...request,
  category: "heating",
  category_label: "Отопление",
  description: "Холодные батареи",
  status: "done",
  timeline: [
    { at: "2026-09-28T11:10:00Z", to_status: "new", by_role: "resident" },
    { at: "2026-09-29T06:30:00Z", to_status: "on_review", by_role: "staff" },
    { at: "2026-09-29T08:00:00Z", to_status: "done", by_role: "resident" },
  ],
};

const assertClean = (text: string) => {
  assert.doesNotMatch(text, /undefined|null|NaN|_/);
  assert.doesNotMatch(text.replace(/\[[^\]\n]+\]/g, ""), /[[\]]/);
  assert.match(text, /\[ФИО\]/);
  assert.match(text, /\[телефон\]/);
};

test("leak act carries the request and the management company", () => {
  const text = leakActLetter(request, house);

  assertClean(text);
  assert.match(text, /Кому: ООО «УК Уютный дом», лицензия № 016-000123/);
  assert.match(text, /г\. Казань, ул\. Пушкина, д\. 10, кв\. 12/);
  assert.match(
    text,
    /заявка №142 от 28\.09\.2026, 14:10, через «Жэка Коммуналкин» в MAX/,
  );
  assert.match(text, /\[перечень повреждений/);
  assert.match(text, /ПП № 354\), п\. 105-106/);
});

test("leak act keeps unknown org and flat in brackets", () => {
  const text = leakActLetter(
    { ...request, flat_number: null },
    { ...house, org: null },
  );

  assertClean(text);
  assert.match(text, /Кому: \[наименование управляющей организации\]/);
  assert.match(text, /кв\. \[номер\]/);
});

test("recalc period ends when the request went on review", () => {
  const text = recalcLetter(heating, house, "management");

  assertClean(text);
  assert.match(text, /с 28\.09\.2026 14:10 по 29\.09\.2026 09:30/);
  assert.match(text, /Кому: ООО «УК Уютный дом»/);
  assert.match(text, /разд\. X и приложение 1/);
});

test("recalc for a utility runs to the present and goes to the supplier", () => {
  const text = recalcLetter(
    { ...request, category: "water_supply", status: "in_progress" },
    house,
    "utility",
  );

  assertClean(text);
  assert.match(text, /с 28\.09\.2026 14:10 \[по настоящее время\]/);
  assert.match(
    text,
    /Кому: \[наименование ресурсоснабжающей организации из квитанции\]/,
  );
});

test("only a leak and the utility outages get a letter", () => {
  const title = (category: string) =>
    requestLetter({ ...request, category }, house, "management")?.title ?? null;

  assert.equal(title("leak"), "Заявление на акт о протечке");
  assert.equal(title("heating"), "Заявление на перерасчет");
  assert.equal(title("water_supply"), "Заявление на перерасчет");
  assert.equal(title("electricity"), "Заявление на перерасчет");
  assert.equal(title("elevator"), null);
  assert.equal(title("charge_dispute"), null);
});

test("recalc runs to the present when the resident rejected the work", () => {
  const text = recalcLetter(
    { ...heating, completion_reason: "resident_rejected" },
    house,
    "management",
  );

  assertClean(text);
  assert.match(text, /с 28\.09\.2026 14:10 \[по настоящее время\]/);
});
