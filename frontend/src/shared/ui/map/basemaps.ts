import type {
  LayerSpecification,
  StyleSpecification,
  TransformStyleFunction,
} from "maplibre-gl";

const OFM = "https://tiles.openfreemap.org";

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
    id: "grey",
    label: "Тёмно-серая",
    kind: "vector",
    style: `${OFM}/styles/dark`,
    swatch: ["#2b2b2b", "#5a5a5a"],
    paint: {
      background: { "background-color": "#2b2b2b" },
      water: { "fill-color": "#0c0c0c" },
      waterway: { "line-color": "#0c0c0c" },
      landcover_ice_shelf: { "fill-color": "#2b2b2b" },
      landcover_glacier: { "fill-color": "#2b2b2b" },
      landuse_residential: { "fill-color": "#2f2f2f" },
      landcover_wood: { "fill-color": "#313331" },
      landuse_park: { "fill-color": "#313331" },
      building: { "fill-color": "#363636", "fill-outline-color": "#414141" },
      road_area_pier: { "fill-color": "#2b2b2b" },
      road_pier: { "line-color": "#2b2b2b" },
      "aeroway-area": { "fill-color": "#353535" },
      "aeroway-runway": { "line-color": "#454545" },
      "aeroway-taxiway": { "line-color": "#404040" },
      highway_path: { "line-color": "#3e3e3e" },
      highway_minor: { "line-color": "#454545" },
      highway_major_casing: { "line-color": "#3a3a3a" },
      highway_major_inner: { "line-color": "#585858" },
      highway_major_subtle: { "line-color": "#4e4e4e" },
      highway_motorway_casing: { "line-color": "#3a3a3a" },
      highway_motorway_inner: { "line-color": "#626262" },
      highway_motorway_subtle: { "line-color": "#4e4e4e" },
      railway_transit: { "line-color": "#474747" },
      railway_minor: { "line-color": "#474747" },
      railway: { "line-color": "#474747" },
      railway_transit_dashline: { "line-color": "#2b2b2b" },
      railway_minor_dashline: { "line-color": "#2b2b2b" },
      railway_dashline: { "line-color": "#2b2b2b" },
      boundary_state: { "line-color": "#555555" },
      "boundary_country_z0-4": { "line-color": "#5a5a5a" },
      "boundary_country_z5-": { "line-color": "#5a5a5a" },
      water_name: { "text-color": "#8c8c8c", "text-halo-color": "#0c0c0c" },
      highway_name_other: {
        "text-color": "#9e9e9e",
        "text-halo-color": "#242424",
      },
      highway_name_motorway: { "text-color": "#a8a8a8" },
      place_other: { "text-color": "#bdbdbd" },
      place_suburb: { "text-color": "#bdbdbd" },
      place_village: { "text-color": "#bdbdbd" },
      place_town: { "text-color": "#c8c8c8" },
      place_city: { "text-color": "#d2d2d2" },
      place_city_large: { "text-color": "#d2d2d2" },
      place_state: { "text-color": "#bdbdbd" },
      place_country_other: { "text-color": "#bdbdbd" },
      place_country_minor: { "text-color": "#bdbdbd" },
      place_country_major: { "text-color": "#c8c8c8" },
    },
  },
  {
    id: "dark",
    label: "Чёрная",
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
    swatch: ["#f2efe9", "#aad3df"],
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
    choice === "auto" ? (scheme === "dark" ? "grey" : "light") : choice;
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
          },
        },
        layers: [{ id: "base", type: "raster", source: "base" }],
      };

export const restyleOf =
  (basemap: Basemap): TransformStyleFunction =>
  (_previous, next) => {
    if (!("paint" in basemap)) {
      return next;
    }

    const paint: Partial<Record<string, object>> = basemap.paint;

    return {
      ...next,
      layers: next.layers.map((layer) => {
        const override = paint[layer.id];

        return override && "paint" in layer
          ? ({
              ...layer,
              paint: { ...layer.paint, ...override },
            } as LayerSpecification)
          : layer;
      }),
    };
  };
