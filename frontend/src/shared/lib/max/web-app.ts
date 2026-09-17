export type MaxPlatform = "ios" | "android" | "desktop" | "web";

export type MaxEntryPoint = "tabbar" | "default";

export interface MaxBridgeError {
  error: { code: string };
}

export interface MaxBackButton {
  readonly isVisible: boolean;
  show(): void;
  hide(): void;
  onClick(callback: () => void): void;
  offClick(callback: () => void): void;
}

export interface MaxContact {
  phone: string;
  authDate: string;
  hash: string;
}

export interface MaxShareText {
  text?: string;
  link?: string;
}

export interface MaxShareMessage {
  mid: string;
  chatType: "DIALOG" | "CHAT";
}

export interface MaxWebApp {
  readonly initData: string | null;
  readonly initDataUnsafe: unknown;
  readonly platform: MaxPlatform | null;
  readonly version: string | null;
  readonly deviceName: string | null;
  readonly BackButton: MaxBackButton;

  ready(): void;
  close(): void;
  getLaunchContext(): Promise<{ entryPoint: MaxEntryPoint }>;
  getViewportSize(): Promise<{ height: string; width: string }>;
  requestContact(): Promise<MaxContact>;
  openLink(url: string): void;
  openMaxLink(url: string): void;
  downloadFile(url: string, fileName: string): Promise<void>;
  shareContent(params: MaxShareText): Promise<void>;
  shareMaxContent(params: MaxShareText | MaxShareMessage): Promise<void>;
  openCodeReader(fileSelect?: boolean): Promise<string>;
  enableClosingConfirmation(): void;
  disableClosingConfirmation(): void;
}

declare global {
  interface Window {
    WebApp?: MaxWebApp;
  }
}

export const getWebApp = (): MaxWebApp | null => window.WebApp ?? null;
