import { lazy } from "react";

export type { BasemapId } from "./basemaps";
export { type MapSettings, useMapSettings } from "./map-settings";
export type {
  MapBounds,
  MapClick,
  MapFocus,
  MapPoint,
  MapViewProps,
} from "./map-view";
export { MapSettingsSheet, type MapSettingsSheetProps } from "./settings-sheet";
export { hasWebGL } from "./tiles";
export { type MapTone, TONE_COLORS } from "./tones";

export const MapView = lazy(() => import("./map-view"));
