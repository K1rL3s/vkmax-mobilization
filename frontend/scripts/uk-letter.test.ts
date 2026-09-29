import assert from "node:assert/strict";
import { test } from "node:test";

process.env.TZ = "Europe/Moscow";

const ukLetterUrl = new URL(
  "../src/features/home/uk-letter.ts",
  import.meta.url,
).href;

type Letter = { subject: string; body: string };

const { ukLetter, ukMailto } = (await import(ukLetterUrl)) as {
  ukLetter: (...args: unknown[]) => Letter;
  ukMailto: (email: string, letter: Letter) => string;
};

const org = {
  id: 1,
  name: 'ООО "УЮТСЕРВИС"',
  phone: "+78432022808",
  address: "г. Казань, ул. Роторная, д. 1",
  email: "oooyutservis@mail.ru",
};

const address = "Казань, проспект Победы, 17";

test("names the УК, the house, the flat and the answer term", () => {
  const letter = ukLetter(org, address, "12", "  Течёт крыша над 9 этажом ");

  assert.equal(letter.subject, `Обращение жителя дома ${address}`);
  assert.match(
    letter.body,
    /^Кому: ООО "УЮТСЕРВИС", г\. Казань, ул\. Роторная, д\. 1$/m,
  );
  assert.match(
    letter.body,
    /^От: \[ФИО\], Казань, проспект Победы, 17, кв\. 12, /m,
  );
  assert.match(letter.body, /^Течёт крыша над 9 этажом$/m);
  assert.match(letter.body, /10 рабочих дней .*ПП РФ № 416, п\. 35, 36/);
  assert.match(letter.body, /^Дата: \d\d\.\d\d\.\d{4}$/m);
  assert.doesNotMatch(letter.body, /undefined|null|Жэка/);
});

test("leaves blanks for what the resident has not given", () => {
  const letter = ukLetter({ ...org, address: "" }, address, null, " ");

  assert.match(letter.body, /^Кому: ООО "УЮТСЕРВИС"$/m);
  assert.match(letter.body, /кв\. \[номер\]/);
  assert.match(letter.body, /^\[Опишите, что случилось\]$/m);
});

test("keeps the whole text in the mail link", () => {
  const letter = ukLetter(
    org,
    address,
    "12",
    "Счёт #5 & долг? 100%\nвторая строка",
  );
  const link = new URL(ukMailto(org.email, letter));

  assert.equal(link.protocol, "mailto:");
  assert.equal(link.pathname, org.email);
  assert.equal(link.searchParams.get("subject"), letter.subject);
  assert.equal(link.searchParams.get("body"), letter.body);
});
