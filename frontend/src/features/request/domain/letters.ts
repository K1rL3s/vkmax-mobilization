import type { HouseCard } from "@/features/house";

import type { RequestCard, ResponsibilityZone } from "./types";

export type Letter = { title: string; hint: string; text: string };

const docDate = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

const docTime = new Intl.DateTimeFormat("ru-RU", {
  hour: "2-digit",
  minute: "2-digit",
});

const day = (value: string | number) => docDate.format(new Date(value));

const time = (value: string) => docTime.format(new Date(value));

const managementOrg = (house: HouseCard) =>
  house.org
    ? `${house.org.name}${house.org.license_no ? `, лицензия № ${house.org.license_no}` : ""}, адрес: ${house.org.address}`
    : "[наименование управляющей организации]";

const flatAddress = (request: RequestCard, house: HouseCard) =>
  `${house.address}, кв. ${request.flat_number ?? "[номер]"}`;

const letter = (
  to: string,
  title: string,
  body: string[],
  request: RequestCard,
  house: HouseCard,
) =>
  [
    `Кому: ${to}`,
    `От: [ФИО], проживающего(ей) по адресу: ${flatAddress(request, house)}. Тел.: [телефон]`,
    "",
    title,
    "",
    ...body.flatMap((paragraph) => [paragraph, ""]),
    `Дата: ${day(Date.now())}`,
    "Подпись: [подпись]",
  ].join("\n");

const dispatchLine = (request: RequestCard) =>
  `Обращение в аварийно-диспетчерскую службу: заявка №${request.id} от ${day(request.created_at)}, ${time(request.created_at)}, через «Жэка Коммуналкин» в MAX.`;

export const leakActLetter = (request: RequestCard, house: HouseCard) =>
  letter(
    managementOrg(house),
    "ЗАЯВЛЕНИЕ О СОСТАВЛЕНИИ АКТА",
    [
      `Прошу направить комиссию и составить акт о протечке в квартире по адресу: ${flatAddress(request, house)}.`,
      `Описание из заявки: «${request.description}».`,
      dispatchLine(request),
      "Обнаруженные повреждения: [перечень повреждений: что пострадало, площадь, есть ли фото].",
      "Прошу указать в акте причину и источник протечки, а также перечень повреждений. Копию акта прошу выдать мне.",
      "Основание: Правила предоставления коммунальных услуг (ПП № 354), п. 105-106.",
    ],
    request,
    house,
  );

const violationEnd = (request: RequestCard) => {
  if (
    (request.status !== "on_review" && request.status !== "done") ||
    request.completion_reason === "resident_rejected"
  ) {
    return null;
  }

  return (
    request.timeline.findLast((entry) => entry.to_status === "on_review") ??
    request.timeline.findLast((entry) => entry.to_status === "done")
  )?.at;
};

export const recalcLetter = (
  request: RequestCard,
  house: HouseCard,
  zone: ResponsibilityZone | null,
) => {
  const end = violationEnd(request);

  return letter(
    zone === "utility"
      ? "[наименование ресурсоснабжающей организации из квитанции]"
      : managementOrg(house),
    "ЗАЯВЛЕНИЕ О ПЕРЕРАСЧЕТЕ ПЛАТЫ",
    [
      `Сообщаю о нарушении качества коммунальной услуги по адресу: ${flatAddress(request, house)}. ${request.category_label}: «${request.description}».`,
      `Период нарушения: с ${day(request.created_at)} ${time(request.created_at)} ${end ? `по ${day(end)} ${time(end)}` : "[по настоящее время]"}.`,
      "Замеры и подтверждения: [например, температура в комнате, фото].",
      dispatchLine(request),
      "Прошу зафиксировать факт нарушения актом и выполнить перерасчет платы за период нарушения. Копию акта прошу выдать мне.",
      "Основание: Правила предоставления коммунальных услуг (ПП № 354), разд. X и приложение 1.",
    ],
    request,
    house,
  );
};

export const requestLetter = (
  request: RequestCard,
  house: HouseCard,
  zone: ResponsibilityZone | null,
): Letter | null => {
  if (request.category === "leak") {
    return {
      title: "Заявление на акт о протечке",
      hint: "Акт подтверждает ущерб от протечки. Мы подставили данные заявки, недостающее отмечено [в скобках]",
      text: leakActLetter(request, house),
    };
  }

  if (["water_supply", "heating", "electricity"].includes(request.category)) {
    return {
      title: "Заявление на перерасчет",
      hint: "За время перебоев плату можно снизить. Мы подставили данные заявки, недостающее отмечено [в скобках]",
      text: recalcLetter(request, house, zone),
    };
  }

  return null;
};
