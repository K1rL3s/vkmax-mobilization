interface MaxShareText {
  text?: string;
  link?: string;
}

interface MaxWebApp {
  readonly initData: string | null;
  readonly initDataUnsafe: unknown;
  readonly platform?: string | null;
  readonly BackButton?: {
    show(): void;
    hide(): void;
    onClick(callback: () => void): void;
    offClick(callback: () => void): void;
  };
  readonly HapticFeedback?: {
    notificationOccurred(
      type: "error" | "success" | "warning",
    ): Promise<unknown>;
    selectionChanged(): Promise<unknown>;
  };

  close(): void;
  shareMaxContent(params: MaxShareText): Promise<void>;
  requestContact?(): Promise<unknown>;
  enableClosingConfirmation?(): void;
  disableClosingConfirmation?(): void;
}

declare global {
  interface Window {
    WebApp?: MaxWebApp;
  }
}

export const getWebApp = (): MaxWebApp | null => window.WebApp ?? null;
