interface MaxShareText {
  text?: string;
  link?: string;
}

interface MaxWebApp {
  readonly initData: string | null;
  readonly initDataUnsafe: unknown;
  readonly BackButton: {
    show(): void;
    hide(): void;
    onClick(callback: () => void): void;
    offClick(callback: () => void): void;
  };

  close(): void;
  shareMaxContent(params: MaxShareText): Promise<void>;
}

declare global {
  interface Window {
    WebApp?: MaxWebApp;
  }
}

export const getWebApp = (): MaxWebApp | null => window.WebApp ?? null;
