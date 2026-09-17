import { z } from "zod";

import { getWebApp, type MaxPlatform } from "./web-app";

const maxUserSchema = z
  .object({
    id: z.number().int(),
    first_name: z.string(),
    last_name: z.string().nullish().catch(null),
    username: z.string().nullish().catch(null),
    language_code: z.string().nullish().catch(null),
    photo_url: z.url().nullish().catch(null),
  })
  .transform((user) => ({
    id: user.id,
    firstName: user.first_name,
    lastName: user.last_name ?? null,
    fullName: [user.first_name, user.last_name].filter(Boolean).join(" "),
    username: user.username ?? null,
    languageCode: user.language_code ?? null,
    photoUrl: user.photo_url ?? null,
  }));

const maxChatTypeSchema = z.enum(["DIALOG", "CHAT", "CHANNEL"]);

const maxChatSchema = z.object({
  id: z.number(),
  type: maxChatTypeSchema,
});

const initDataSchema = z.object({
  user: maxUserSchema.nullish().catch(null),
  chat: maxChatSchema.nullish().catch(null),
  start_param: z.string().nullish().catch(null),
});

export type MaxChatType = z.infer<typeof maxChatTypeSchema>;

export type MaxUser = z.infer<typeof maxUserSchema>;

export type MaxChat = z.infer<typeof maxChatSchema>;

export interface MaxLaunch {
  isInsideMax: boolean;
  initData: string | null;
  platform: MaxPlatform | null;
  version: string | null;
  deviceName: string | null;
  user: MaxUser | null;
  chat: MaxChat | null;
  startParam: string | null;
}

const OUTSIDE_MAX: MaxLaunch = {
  isInsideMax: false,
  initData: null,
  platform: null,
  version: null,
  deviceName: null,
  user: null,
  chat: null,
  startParam: null,
};

const readLaunch = (): MaxLaunch => {
  const webApp = getWebApp();

  if (!webApp?.initData) {
    return OUTSIDE_MAX;
  }

  const initData = initDataSchema.safeParse(webApp.initDataUnsafe);

  return {
    isInsideMax: true,
    initData: webApp.initData,
    platform: webApp.platform,
    version: webApp.version,
    deviceName: webApp.deviceName,
    user: initData.data?.user ?? null,
    chat: initData.data?.chat ?? null,
    startParam: initData.data?.start_param ?? null,
  };
};

let launch: MaxLaunch | null = null;

export const getMaxLaunch = (): MaxLaunch => (launch ??= readLaunch());

export const getInitData = (): string | null => getMaxLaunch().initData;
