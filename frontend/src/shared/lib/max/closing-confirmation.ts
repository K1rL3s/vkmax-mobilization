import { useEffect } from "react";

import { getWebApp } from "./web-app";

export const useClosingConfirmation = (active: boolean) => {
  useEffect(() => {
    if (!active) {
      return;
    }

    const webApp = getWebApp();
    webApp?.enableClosingConfirmation?.();

    return () => webApp?.disableClosingConfirmation?.();
  }, [active]);
};
