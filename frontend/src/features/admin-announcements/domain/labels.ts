import type { components } from "@/shared/api/schema/generated";
import { plural } from "@/shared/lib/format";

export type Channel = components["schemas"]["AnnouncementChannel"];

type House = { id: number; address: string };

const CHANNEL_LABELS: Record<Channel, string> = {
  chat: "Чат дома",
  direct: "Личные сообщения",
};

export const channelsLabel = (channels: Channel[]) =>
  channels.map((channel) => CHANNEL_LABELS[channel]).join(", ");

export const housesCount = (count: number) =>
  `${count} ${plural(count, ["дом", "дома", "домов"])}`;

export const recipientsCount = (count: number) =>
  `${count} ${plural(count, ["адресат", "адресата", "адресатов"])}`;

export const addressees = (houseIds: number[], houses: House[]) => {
  if (houseIds.length === 1) {
    const house = houses.find(({ id }) => id === houseIds[0]);

    if (house) {
      return house.address;
    }
  }

  if (houses.length > 0 && houses.every(({ id }) => houseIds.includes(id))) {
    return "Все дома";
  }

  return housesCount(houseIds.length);
};

type Delivery = components["schemas"]["AnnouncementItem"];

export const isSending = (delivery: Delivery) =>
  delivery.delivered_count === null &&
  Date.now() - Date.parse(delivery.created_at) < 10 * 60 * 1000;

export const deliveryLabel = (delivery: Delivery) => {
  if (isSending(delivery)) {
    return "Отправляется…";
  }

  if (delivery.delivered_count === null) {
    return recipientsCount(delivery.recipients_count);
  }

  return `Доставлено ${delivery.delivered_count} из ${delivery.recipients_count}`;
};

export const undeliveredReason = ({ channels }: Delivery) =>
  [
    channels.includes("direct") &&
      "жители остановили бота, выключили объявления или ни разу его не открывали",
    channels.includes("chat") && "у бота нет прав администратора в чате дома",
  ]
    .filter(Boolean)
    .join(", или ");
