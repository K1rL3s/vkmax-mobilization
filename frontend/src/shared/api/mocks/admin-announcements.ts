import type { components } from "../schema/generated";

import { badRequest, endpoint, notFound, number, ok, page } from "./reply";
import { ZHILSERVIS, hours } from "./state";

type Schemas = components["schemas"];

type Item = Schemas["AnnouncementItem"];

type Channel = Schemas["AnnouncementChannel"];

const ORG_HOUSES: Record<number, { residents: number; chatBound: boolean }> = {
  1: { residents: 86, chatBound: true },
  2: { residents: 31, chatBound: false },
  3: { residents: 12, chatBound: true },
};

const deliver = (houseIds: number[], channels: Channel[]) => {
  const withoutChat = channels.includes("chat")
    ? houseIds.filter((id) => !ORG_HOUSES[id].chatBound)
    : [];
  const chats = channels.includes("chat")
    ? houseIds.length - withoutChat.length
    : 0;
  const residents = channels.includes("direct")
    ? houseIds.reduce((sum, id) => sum + ORG_HOUSES[id].residents, 0)
    : 0;

  return {
    recipients: chats + residents,
    delivered: chats + Math.round(residents * 0.85),
    withoutChat,
  };
};

const item = (
  id: number,
  hoursAgo: number,
  houseIds: number[],
  channels: Channel[],
  text: string,
  urgent = false,
): Item => ({
  id,
  created_at: hours(-hoursAgo),
  text,
  house_ids: houseIds,
  channels,
  org_name: ZHILSERVIS.name,
  recipients_count: deliver(houseIds, channels).recipients,
  delivered_count:
    hoursAgo === 0 ? null : deliver(houseIds, channels).delivered,
  urgent,
});

const announcements: Item[] = [
  item(
    8,
    2,
    [1],
    ["chat", "direct"],
    "Авария на водопроводе: в доме нет холодной воды. Аварийная бригада уже на месте, воду дадут до 18:00",
    true,
  ),
  item(
    7,
    26,
    [1, 2, 3],
    ["chat"],
    "Завтра с 10:00 до 13:00 уборка придомовой территории. Просим убрать машины с парковки у подъездов",
  ),
  item(
    6,
    3 * 24,
    [2, 3],
    ["chat", "direct"],
    "В четверг проведём осмотр чердаков и кровли перед зимой. Доступ на технический этаж понадобится с 10:00 до 16:00",
  ),
  item(
    5,
    5 * 24,
    [1, 2, 3],
    ["direct"],
    "Отключение отопления 26 сентября с 9:00 до 15:00: ремонт на теплотрассе. Горячая вода будет",
    true,
  ),
  item(
    4,
    7 * 24,
    [3],
    ["chat"],
    "Лифт во втором подъезде снова работает, спасибо за терпение",
  ),
  item(
    3,
    10 * 24,
    [1, 3],
    ["chat"],
    "Уважаемые жители!\nС 1 октября начинается отопительный сезон.\nЕсли к 5 октября батареи останутся холодными, оставьте заявку в приложении, и мастер проверит стояк.\n\nПросим заранее проверить, закрыты ли окна в подъездах и подвалах: сквозняк остужает стояки, и батареи на верхних этажах прогреваются дольше.",
  ),
  item(
    2,
    14 * 24,
    [2],
    ["direct"],
    "Показания счётчиков за сентябрь принимаются до 25 числа. Передать их можно в разделе «Показания»",
  ),
  item(
    1,
    20 * 24,
    [1, 2, 3],
    ["chat"],
    "Изменились часы приёма УК: вторник и четверг с 15:00 до 19:00",
  ),
];

export const adminAnnouncementsConfigs = [
  endpoint("get", "/admin/announcements", (request) => {
    const houseId = number(request.query.house_id);
    const found = page(
      announcements.filter(
        (announcement) =>
          houseId === null || announcement.house_ids.includes(houseId),
      ),
      request.query,
    );

    return houseId !== null && !(houseId in ORG_HOUSES)
      ? notFound("Дом не найден")
      : ok(found satisfies Schemas["Page_AnnouncementItem_"]);
  }),
  endpoint("post", "/admin/announcements", (request) => {
    const body = request.body as Partial<Schemas["CreateAnnouncementRequest"]>;
    const text = typeof body.text === "string" ? body.text.trim() : "";
    const houseIds = [...new Set(body.house_ids ?? [])];
    const channels = [...new Set(body.channels ?? ["chat" as const])];

    if (!text) {
      return badRequest("Напишите текст объявления");
    }

    if (text.length > 2000) {
      return badRequest("Сократите объявление до 2000 символов");
    }

    if (houseIds.length === 0) {
      return badRequest("Выберите хотя бы один дом");
    }

    if (channels.length === 0) {
      return badRequest("Выберите хотя бы один канал");
    }

    if (houseIds.some((id) => !(id in ORG_HOUSES))) {
      return notFound("Дом не найден");
    }

    const created = item(
      Math.max(0, ...announcements.map(({ id }) => id)) + 1,
      0,
      houseIds,
      channels,
      text,
      body.urgent ?? false,
    );
    announcements.unshift(created);

    return ok({
      ...created,
      houses_without_chat: deliver(houseIds, channels).withoutChat,
    } satisfies Item);
  }),
];
