import type { components } from "@/shared/api/schema/generated";

type RequestChannel = components["schemas"]["RequestChannel"];

// подписи каналов заявки; у блока У1 будет свой словарь на те же ключи -
// расхождение описано в `.scratch/design-sync.md`
export const CHANNEL_LABEL: Record<RequestChannel, string> = {
  miniapp: "Мини-апп",
  bot: "Бот",
  chat: "Чат дома",
  phone: "Звонок",
};
