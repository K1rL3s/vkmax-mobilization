import type { StyleSpecification } from "maplibre-gl";

const OFM = "https://tiles.openfreemap.org";
const OSM_ATTRIBUTION =
  '© <a href="https://www.openstreetmap.org/copyright" target="_blank">участники OpenStreetMap</a>';

export const BASEMAPS = [
  {
    id: "light",
    label: "Светлая",
    kind: "vector",
    style: `${OFM}/styles/positron`,
    swatch: ["#f4f3ef", "#cfd6dd"],
  },
  {
    id: "bright",
    label: "Яркая",
    kind: "vector",
    style: `${OFM}/styles/bright`,
    swatch: ["#f8f4e8", "#8fc1e8"],
  },
  {
    id: "liberty",
    label: "Объёмная",
    kind: "vector",
    style: `${OFM}/styles/liberty`,
    swatch: ["#efe9e1", "#e0cfb8"],
  },
  {
    id: "dark",
    label: "Тёмная",
    kind: "vector",
    style: `${OFM}/styles/dark`,
    swatch: ["#1c1f24", "#3a3f47"],
  },
  {
    id: "fiord",
    label: "Ночная синяя",
    kind: "vector",
    style: `${OFM}/styles/fiord`,
    swatch: ["#2b3a4f", "#4d6a8a"],
  },
  {
    id: "osm",
    label: "OSM классическая",
    kind: "raster",
    tiles: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    maxzoom: 19,
    attribution: OSM_ATTRIBUTION,
    swatch: ["#f2efe9", "#aad3df"],
  },
  {
    id: "topo",
    label: "Топографическая",
    kind: "raster",
    tiles: "https://a.tile.opentopomap.org/{z}/{x}/{y}.png",
    maxzoom: 17,
    attribution: `Картография © <a href="https://opentopomap.org" target="_blank">OpenTopoMap</a> (CC-BY-SA), данные ${OSM_ATTRIBUTION}, SRTM`,
    swatch: ["#e8efd9", "#c9b48c"],
  },
] as const;

export type Basemap = (typeof BASEMAPS)[number];
export type BasemapId = Basemap["id"];

export const GLYPHS = `${OFM}/fonts/{fontstack}/{range}.pbf`;

export const resolveBasemap = (
  choice: "auto" | BasemapId,
  scheme: "light" | "dark",
): Basemap => {
  const id =
    choice === "auto" ? (scheme === "dark" ? "dark" : "light") : choice;
  return BASEMAPS.find((basemap) => basemap.id === id) ?? BASEMAPS[0];
};

export const styleOf = (basemap: Basemap): string | StyleSpecification =>
  basemap.kind === "vector"
    ? basemap.style
    : {
        version: 8,
        glyphs: GLYPHS,
        sources: {
          base: {
            type: "raster",
            tiles: [basemap.tiles],
            tileSize: 256,
            maxzoom: basemap.maxzoom,
            attribution: basemap.attribution,
          },
        },
        layers: [{ id: "base", type: "raster", source: "base" }],
      };
