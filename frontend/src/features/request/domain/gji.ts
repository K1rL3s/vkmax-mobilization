import type { HouseCard } from "@/features/house";

import { duration, plural } from "@/shared/lib/format";
import { STATUS_LABEL } from "./status";
import type { RequestCard } from "./types";

const docDate = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

const docTime = new Intl.DateTimeFormat("ru-RU", {
  hour: "2-digit",
  minute: "2-digit",
});

const at = (value: string) =>
  `${docDate.format(new Date(value))} в ${docTime.format(new Date(value))}`;

export const gjiAppeal = (request: RequestCard, house: HouseCard) => {
  const now = Date.now();
  const org = house.org;
  const flat = request.flat_number ? `, кв. ${request.flat_number}` : "";
  const license = org?.license_no ? `, лицензия № ${org.license_no}` : "";
  const overdue = request.deadline_at
    ? duration(now - new Date(request.deadline_at).getTime())
    : null;

  return [
    "В государственную жилищную инспекцию",
    `субъект РФ: ${house.region}`,
    "",
    "От: _______________ (ФИО)",
    `Адрес: ${house.address}${flat}`,
    "Контакт для ответа: _______________",
    "",
    org &&
      `Управляющая организация: ${org.name}${license}, адрес: ${org.address}.`,
    org && "",
    `${at(request.created_at)} через мини-приложение «Жэка Коммуналкин» в мессенджере MAX я подал(а) в управляющую организацию заявку №${request.id} по категории «${request.category_label}».`,
    "",
    `Срок реакции по этой категории в сервисе - ${request.normative_hours} ${plural(request.normative_hours, ["час", "часа", "часов"])}.` +
      (request.deadline_at ? ` Срок истёк ${at(request.deadline_at)}.` : "") +
      (overdue ? ` Просрочка на момент обращения - ${overdue}.` : "") +
      ` Заявка находится в статусе «${STATUS_LABEL[request.status]}», работы не завершены.`,
    "",
    "Прошу провести проверку по изложенным фактам и обязать управляющую организацию устранить нарушение.",
    "",
    `Дата: ${docDate.format(now)}`,
  ]
    .filter((line) => typeof line === "string")
    .join("\n");
};
