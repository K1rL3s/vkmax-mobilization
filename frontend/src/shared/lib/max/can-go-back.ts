export const canGoBack = (handlerCount: number, historyState: unknown) =>
  handlerCount > 0 &&
  typeof historyState === "object" &&
  historyState !== null &&
  "idx" in historyState &&
  typeof historyState.idx === "number" &&
  historyState.idx > 0;
