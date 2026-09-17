export { getWebApp } from "./web-app";
export type {
  MaxBackButton,
  MaxBridgeError,
  MaxContact,
  MaxEntryPoint,
  MaxPlatform,
  MaxShareMessage,
  MaxShareText,
  MaxWebApp,
} from "./web-app";

export { getInitData, getMaxLaunch } from "./launch";
export type { MaxChat, MaxChatType, MaxLaunch, MaxUser } from "./launch";

export { useMaxLaunch, useMaxUser } from "./use-max-launch";
export {
  useBackButton,
  useBackNavigation,
  type UseBackButtonOptions,
} from "./use-back-button";
