import type { components } from "@/shared/api/schema/generated";
import { plural } from "@/shared/lib/format";

export type Channel = components["schemas"]["AnnouncementChannel"];

type House = { id: number; address: string };

export const CHANNEL_LABELS: Record<Channel, string> = {
  chat: "Чат дома",
  direct: "Личные сообщения",
};

export const channelsLabel = (channels: Channel[]) =>
  channels.map((channel) => CHANNEL_LABELS[channel]).join(", ");

export const housesCount = (count: number) =>
  `${count} ${plural(count, ["дом", "дома", "домов"])}`;

export const recipientsCount = (count: number) =>
  `${count} ${plural(count, ["адресат", "адресата", "адресатов"])}`;

// houses - все дома организации: без них адрес и «Все дома» не узнать
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
