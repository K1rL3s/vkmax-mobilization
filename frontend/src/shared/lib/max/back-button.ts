import { canGoBack } from "./can-go-back";
import { getWebApp } from "./web-app";

type BackHandler = () => void;

const handlers: BackHandler[] = [];

let dispatchAttached = false;
let syncScheduled = false;

const dispatch = () => {
  handlers.at(-1)?.();
};

const sync = () => {
  const backButton = getWebApp()?.BackButton;

  if (!backButton) {
    return;
  }

  const visible = canGoBack(handlers.length, window.history.state);

  if (visible && !dispatchAttached) {
    backButton.onClick(dispatch);
    backButton.show();
    dispatchAttached = true;
    return;
  }

  if (!visible && dispatchAttached) {
    backButton.offClick(dispatch);
    backButton.hide();
    dispatchAttached = false;
  }
};

const scheduleSync = () => {
  if (syncScheduled) {
    return;
  }

  syncScheduled = true;

  queueMicrotask(() => {
    syncScheduled = false;
    sync();
  });
};

export const pushBackHandler = (handler: BackHandler) => {
  handlers.push(handler);
  scheduleSync();

  return () => {
    handlers.splice(handlers.lastIndexOf(handler), 1);
    scheduleSync();
  };
};
