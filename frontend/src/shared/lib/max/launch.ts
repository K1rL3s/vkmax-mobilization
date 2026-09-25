import { z } from "zod";

import { getWebApp } from "./web-app";

const initDataSchema = z.object({
  start_param: z.string().nullish().catch(null),
});

const readLaunch = () => {
  const webApp = getWebApp();

  if (!webApp?.initData) {
    return { isInsideMax: false, initData: null, startParam: null };
  }

  return {
    isInsideMax: true,
    initData: webApp.initData,
    startParam:
      initDataSchema.safeParse(webApp.initDataUnsafe).data?.start_param ?? null,
  };
};

let launch: ReturnType<typeof readLaunch> | null = null;

export const getMaxLaunch = () => (launch ??= readLaunch());
