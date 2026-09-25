import type { components } from "@/shared/api/schema/generated";

type RequestChannel = components["schemas"]["RequestChannel"];

// подписи каналов заявки; у заявок УК свой словарь на те же ключи - сводить
// их в `shared` на третьем потребителе
export const CHANNEL_LABEL: Record<RequestChannel, string> = {
  miniapp: "Мини-апп",
  bot: "Бот",
  chat: "Чат дома",
  phone: "Звонок",
};
