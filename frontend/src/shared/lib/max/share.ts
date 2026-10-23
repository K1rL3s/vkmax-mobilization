import { getWebApp, type MaxShareText } from "./web-app";

export const shareToMax = (content: MaxShareText) => {
  getWebApp()
    ?.shareMaxContent(content)
    .catch(() => undefined);
};
