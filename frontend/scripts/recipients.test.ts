import assert from "node:assert/strict";
import { test } from "node:test";

const recipientsUrl = new URL(
  "../src/features/request/domain/recipients.ts",
  import.meta.url,
).href;

type Recipient = {
  who: string;
  when: string;
  how: string;
  topics: (readonly [string, string])[];
};

const { complaintRecipients } = (await import(recipientsUrl)) as {
  complaintRecipients: (category: string) => Recipient[];
};

const categories = [
  "leak",
  "water_supply",
  "heating",
  "electricity",
  "elevator",
  "garbage",
  "entrance",
  "yard",
  "meter_error",
  "charge_dispute",
  "other",
];

const codes = (recipient: Recipient | undefined) =>
  recipient?.topics.map(([code]) => code);

test("every overdue request names the inspection with the ignored-request topic and ends with the prosecutor", () => {
  for (const category of categories) {
    const recipients = complaintRecipients(category);

    assert.ok(
      codes(recipients.find(({ who }) => who === "ГЖИ"))?.includes("3.13"),
      category,
    );
    assert.equal(recipients.at(-1)?.who, "Прокуратура", category);
  }
});

test("garbage, billing and a lift point where the spec says", () => {
  const who = (category: string) =>
    complaintRecipients(category).map((recipient) => recipient.who);

  assert.deepEqual(who("elevator"), ["ГЖИ", "Прокуратура"]);
  assert.deepEqual(who("garbage"), ["Регоператор ТКО", "ГЖИ", "Прокуратура"]);
  assert.equal(
    complaintRecipients("garbage")[0].when,
    "если не вывозят контейнеры по графику",
  );
  assert.ok(codes(complaintRecipients("garbage")[1])?.includes("2.4"));
  assert.deepEqual(
    codes(
      complaintRecipients("charge_dispute").find(
        (recipient) => recipient.who === "Тарифный орган региона",
      ),
    ),
    ["5.3"],
  );
});
