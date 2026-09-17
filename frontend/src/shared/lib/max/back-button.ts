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

  if (handlers.length > 0 && !dispatchAttached) {
    backButton.onClick(dispatch);
    backButton.show();
    dispatchAttached = true;
    return;
  }

  if (handlers.length === 0 && dispatchAttached) {
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
    const index = handlers.lastIndexOf(handler);

    if (index !== -1) {
      handlers.splice(index, 1);
    }

    scheduleSync();
  };
};
