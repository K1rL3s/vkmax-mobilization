import {
  type ReactNode,
  useEffect,
  useEffectEvent,
  useRef,
  useState,
} from "react";
import { useColorScheme } from "@maxhub/max-ui";
import {
  type ExpressionSpecification,
  type GeoJSONSource,
  Map as MapLibre,
  type MapGeoJSONFeature,
  type MapMouseEvent,
  Marker,
  setWorkerUrl,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

import { cn } from "@/shared/lib/css";

import { resolveBasemap, styleOf } from "./basemaps";
import type { MapSettings } from "./map-settings";
import { hasWebGL, isFatalMapError, proxiedUrl } from "./tiles";
import { type MapTone, TONE_COLORS } from "./tones";

import styles from "./map-view.module.css";

setWorkerUrl(workerUrl);

export type MapPoint = {
  id: number;
  lat: number;
  lon: number;
  tone: MapTone;
  label?: string;
  size?: number;
  weight?: number;
};

export type MapClick = {
  lat: number;
  lon: number;
  building: GeoJSON.Geometry | null;
};

export type MapBounds = {
  west: number;
  south: number;
  east: number;
  north: number;
};

export type MapFocus = { lat: number; lon: number; zoom?: number };

export type MapViewProps = {
  settings: MapSettings;
  points: MapPoint[];
  backgroundPoints?: MapPoint[];
  heat?: boolean;
  selectedId?: number | null;
  pulseIds?: readonly number[];
  highlight?: GeoJSON.Geometry | null;
  initialView: MapFocus;
  focus?: MapFocus | null;
  interactive?: boolean;
  onPointClick?: (id: number) => void;
  onMapClick?: (click: MapClick) => void;
  onViewChange?: (bounds: MapBounds, zoom: number) => void;
  onUnavailable?: () => void;
  className?: string;
  children?: ReactNode;
};

const TONE_COLOR = [
  "match",
  ["get", "tone"],
  ...Object.entries(TONE_COLORS).flat(),
  TONE_COLORS.muted,
] as unknown as ExpressionSpecification;

const PIN_RADIUS: ExpressionSpecification = [
  "interpolate",
  ["linear"],
  ["get", "size"],
  0,
  6,
  20,
  16,
];

const NOT_CLUSTER: ExpressionSpecification = ["!", ["has", "point_count"]];

const visibility = (visible: boolean) => (visible ? "visible" : "none");

const pinRadius = (sizeByCount: boolean) => (sizeByCount ? PIN_RADIUS : 6);

const labelOffset = (sizeByCount: boolean): ExpressionSpecification =>
  sizeByCount
    ? [
        "interpolate",
        ["linear"],
        ["get", "size"],
        0,
        ["literal", [0, 0.8]],
        20,
        ["literal", [0, 1.7]],
      ]
    : ["literal", [0, 0.8]];

const HOUSE_LAYERS = [
  "heat",
  "clusters",
  "cluster-count",
  "pins",
  "pin-labels",
  "selected",
];

const collection = (
  points: readonly MapPoint[],
): GeoJSON.FeatureCollection<GeoJSON.Point> => ({
  type: "FeatureCollection",
  features: points.map((point) => ({
    type: "Feature",
    id: point.id,
    geometry: { type: "Point", coordinates: [point.lon, point.lat] },
    properties: {
      id: point.id,
      tone: point.tone,
      label: point.label ?? "",
      size: point.size ?? 0,
      weight: point.weight ?? 1,
    },
  })),
});

const shape = (
  geometry: GeoJSON.Geometry | null | undefined,
): GeoJSON.FeatureCollection => ({
  type: "FeatureCollection",
  features: geometry ? [{ type: "Feature", geometry, properties: {} }] : [],
});

const selectedFilter = (id: number | null | undefined) =>
  ["==", ["get", "id"], id ?? -1] as ExpressionSpecification;

export const MapViewComponent = ({
  settings,
  points,
  backgroundPoints,
  heat = false,
  selectedId,
  pulseIds,
  highlight,
  initialView,
  focus,
  interactive = true,
  onPointClick,
  onMapClick,
  onViewChange,
  onUnavailable,
  className,
  children,
}: MapViewProps) => {
  const [supported] = useState(hasWebGL);
  const [initial] = useState(() => ({ view: initialView, interactive }));
  const [map, setMap] = useState<MapLibre | null>(null);
  const container = useRef<HTMLDivElement>(null);
  const scheme = useColorScheme();
  const basemap = resolveBasemap(settings.basemap, scheme);
  const threeD = settings.threeD && basemap.kind === "vector";
  const darkBasemap = basemap.id === "dark" || basemap.id === "fiord";
  const pulseKey = pulseIds?.join(",") ?? "";

  const reportUnavailable = useEffectEvent(() => onUnavailable?.());

  const addHouses = useEffectEvent((target: MapLibre) => {
    target.addSource("houses", {
      type: "geojson",
      data: collection(points),
      cluster: settings.cluster,
      clusterRadius: 40,
      clusterProperties: { weight: ["+", ["get", "weight"]] },
    });
    target.addLayer({
      id: "heat",
      type: "heatmap",
      source: "houses",
      layout: { visibility: visibility(heat) },
      paint: {
        "heatmap-weight": ["get", "weight"],
        "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 9, 20, 16, 50],
        "heatmap-opacity": 0.6,
      },
    });
    target.addLayer({
      id: "clusters",
      type: "circle",
      source: "houses",
      filter: ["has", "point_count"],
      paint: {
        "circle-color": TONE_COLORS.brand,
        "circle-radius": ["step", ["get", "point_count"], 14, 10, 18, 50, 22],
        "circle-stroke-width": 5,
        "circle-stroke-color": "rgba(0, 119, 255, 0.3)",
      },
    });
    target.addLayer({
      id: "cluster-count",
      type: "symbol",
      source: "houses",
      filter: ["has", "point_count"],
      layout: {
        "text-field": ["get", "point_count_abbreviated"],
        "text-font": ["Noto Sans Regular"],
        "text-size": 12,
        "text-allow-overlap": true,
      },
      paint: { "text-color": "#ffffff" },
    });
    target.addLayer({
      id: "pins",
      type: "circle",
      source: "houses",
      filter: NOT_CLUSTER,
      paint: {
        "circle-color": TONE_COLOR,
        "circle-radius": pinRadius(settings.sizeByCount),
        "circle-stroke-width": 1.5,
        "circle-stroke-color": "#ffffff",
      },
    });
    target.addLayer({
      id: "pin-labels",
      type: "symbol",
      source: "houses",
      filter: NOT_CLUSTER,
      layout: {
        visibility: visibility(settings.labels),
        "text-field": ["get", "label"],
        "text-font": ["Noto Sans Regular"],
        "text-size": 11,
        "text-anchor": "top",
        "text-offset": labelOffset(settings.sizeByCount),
      },
      paint: {
        "text-color": darkBasemap ? "#ffffff" : "#1c1f24",
        "text-halo-color": darkBasemap ? "#1c1f24" : "#ffffff",
        "text-halo-width": 1.5,
      },
    });
    target.addLayer({
      id: "selected",
      type: "circle",
      source: "houses",
      filter: selectedFilter(selectedId),
      paint: {
        "circle-radius": settings.sizeByCount ? ["+", PIN_RADIUS, 4] : 10,
        "circle-color": "rgba(0, 0, 0, 0)",
        "circle-stroke-width": 3,
        "circle-stroke-color": TONE_COLORS.brand,
      },
    });
  });

  const addAppLayers = useEffectEvent((target: MapLibre) => {
    const layers = target.getStyle().layers;
    for (const layer of layers) {
      if (
        layer.type === "symbol" &&
        JSON.stringify(layer.layout?.["text-field"] ?? "").includes(
          "name:latin",
        )
      ) {
        target.setLayoutProperty(layer.id, "text-field", [
          "coalesce",
          ["get", "name:ru"],
          ["get", "name"],
        ]);
      }
    }

    if (
      basemap.kind === "vector" &&
      target.getSource("openmaptiles") &&
      !layers.some((layer) => layer.type === "fill-extrusion")
    ) {
      target.addLayer(
        {
          id: "extrusion",
          type: "fill-extrusion",
          source: "openmaptiles",
          "source-layer": "building",
          layout: { visibility: visibility(threeD) },
          paint: {
            "fill-extrusion-color": darkBasemap ? "#454b55" : "#c7ccd4",
            "fill-extrusion-height": ["coalesce", ["get", "render_height"], 10],
            "fill-extrusion-base": [
              "coalesce",
              ["get", "render_min_height"],
              0,
            ],
            "fill-extrusion-opacity": 0.7,
          },
        },
        layers[layers.findLastIndex((layer) => layer.type !== "symbol") + 1]
          ?.id,
      );
    }

    target.addSource("picked", { type: "geojson", data: shape(highlight) });
    target.addLayer({
      id: "picked",
      type: "line",
      source: "picked",
      paint: { "line-color": TONE_COLORS.brand, "line-width": 3 },
    });

    target.addSource("background", {
      type: "geojson",
      data: collection(backgroundPoints ?? []),
    });
    target.addLayer({
      id: "background-points",
      type: "circle",
      source: "background",
      paint: {
        "circle-radius": 4,
        "circle-color": TONE_COLOR,
        "circle-stroke-width": 1,
        "circle-stroke-color": "#ffffff",
      },
    });

    addHouses(target);
  });

  const handleClick = useEffectEvent(
    (target: MapLibre, event: MapMouseEvent) => {
      const { x, y } = event.point;
      const layers = ["clusters", "pins", "background-points"].filter((id) =>
        target.getLayer(id),
      );
      const distance = (candidate: MapGeoJSONFeature) => {
        const center = target.project(
          (candidate.geometry as GeoJSON.Point).coordinates as [number, number],
        );
        return Math.hypot(center.x - x, center.y - y);
      };
      const [feature] = [
        ...target.queryRenderedFeatures(event.point, { layers }),
        ...target
          .queryRenderedFeatures(
            [
              [x - 22, y - 22],
              [x + 22, y + 22],
            ],
            { layers },
          )
          .toSorted((a, b) => distance(a) - distance(b)),
      ];

      if (feature?.layer.id === "clusters") {
        const center = (feature.geometry as GeoJSON.Point).coordinates as [
          number,
          number,
        ];
        void target
          .getSource<GeoJSONSource>("houses")
          ?.getClusterExpansionZoom(feature.properties.cluster_id as number)
          .then((zoom) => target.easeTo({ center, zoom }));
        return;
      }

      if (feature) {
        onPointClick?.(feature.properties.id as number);
        return;
      }

      const building = target
        .queryRenderedFeatures(event.point)
        .find((rendered) => rendered.sourceLayer === "building");
      onMapClick?.({
        lat: event.lngLat.lat,
        lon: event.lngLat.lng,
        building: building?.geometry ?? null,
      });
    },
  );

  const reportView = useEffectEvent((target: MapLibre) => {
    const bounds = target.getBounds();
    onViewChange?.(
      {
        west: bounds.getWest(),
        south: bounds.getSouth(),
        east: bounds.getEast(),
        north: bounds.getNorth(),
      },
      target.getZoom(),
    );
  });

  const startPulse = useEffectEvent((target: MapLibre) => {
    const markers = points
      .filter((point) => pulseIds?.includes(point.id))
      .map((point) => {
        const element = document.createElement("div");
        const ring = document.createElement("span");
        ring.className = styles.Pulse;
        ring.style.backgroundColor = TONE_COLORS[point.tone];
        element.append(ring);
        return new Marker({ element })
          .setLngLat([point.lon, point.lat])
          .addTo(target);
      });
    const timer = setTimeout(
      () => markers.forEach((marker) => marker.remove()),
      3000,
    );
    return () => {
      clearTimeout(timer);
      markers.forEach((marker) => marker.remove());
    };
  });

  useEffect(() => {
    if (!supported) {
      reportUnavailable();
      return;
    }
    if (!container.current) return;

    let instance: MapLibre;
    try {
      instance = new MapLibre({
        container: container.current,
        center: [initial.view.lon, initial.view.lat],
        zoom: initial.view.zoom,
        attributionControl: { compact: true },
        locale: {
          "Map.Title": "Карта",
          "AttributionControl.ToggleAttribution": "Источники карты",
        },
        maxPitch: 60,
        interactive: initial.interactive,
        transformRequest: (url) => ({
          url: proxiedUrl(url, window.location.origin),
        }),
      });
    } catch {
      reportUnavailable();
      return;
    }

    let loaded = false;
    const giveUp = () => {
      if (loaded) return;
      loaded = true;
      reportUnavailable();
    };
    const timer = setTimeout(giveUp, 15_000);

    let styled = false;
    instance.on("error", (event) => {
      if (isFatalMapError(event, styled)) giveUp();
    });
    instance.on("load", () => {
      loaded = true;
      clearTimeout(timer);
      reportView(instance);
    });
    instance.on("style.load", () => {
      styled = true;
      addAppLayers(instance);
    });
    instance.on("moveend", () => reportView(instance));
    instance.on("click", (event) => handleClick(instance, event));
    setMap(instance);

    return () => {
      clearTimeout(timer);
      instance.remove();
      setMap(null);
    };
  }, [supported, initial]);

  useEffect(() => {
    map?.setStyle(styleOf(basemap));
  }, [map, basemap]);

  useEffect(() => {
    map?.getSource<GeoJSONSource>("houses")?.setData(collection(points));
  }, [map, points]);

  useEffect(() => {
    map
      ?.getSource<GeoJSONSource>("background")
      ?.setData(collection(backgroundPoints ?? []));
  }, [map, backgroundPoints]);

  useEffect(() => {
    map?.getSource<GeoJSONSource>("picked")?.setData(shape(highlight));
  }, [map, highlight]);

  useEffect(() => {
    if (map?.getLayer("selected")) {
      map.setFilter("selected", selectedFilter(selectedId));
    }
  }, [map, selectedId]);

  useEffect(() => {
    if (map?.getLayer("heat")) {
      map.setLayoutProperty("heat", "visibility", visibility(heat));
    }
  }, [map, heat]);

  useEffect(() => {
    if (map?.getLayer("pin-labels")) {
      map.setLayoutProperty(
        "pin-labels",
        "visibility",
        visibility(settings.labels),
      );
    }
  }, [map, settings.labels]);

  useEffect(() => {
    if (map?.getLayer("pins")) {
      map.setPaintProperty(
        "pins",
        "circle-radius",
        pinRadius(settings.sizeByCount),
      );
      map.setPaintProperty(
        "selected",
        "circle-radius",
        settings.sizeByCount ? ["+", PIN_RADIUS, 4] : 10,
      );
      map.setLayoutProperty(
        "pin-labels",
        "text-offset",
        labelOffset(settings.sizeByCount),
      );
    }
  }, [map, settings.sizeByCount]);

  useEffect(() => {
    if (!map?.getSource("houses")) return;
    HOUSE_LAYERS.forEach((id) => map.removeLayer(id));
    map.removeSource("houses");
    addHouses(map);
  }, [map, settings.cluster]);

  useEffect(() => {
    if (!map) return;
    if (map.getLayer("extrusion")) {
      map.setLayoutProperty("extrusion", "visibility", visibility(threeD));
    }
    map.easeTo({ pitch: threeD ? 55 : 0 });
  }, [map, threeD]);

  useEffect(() => {
    if (!map || !focus) return;
    map.flyTo({
      center: [focus.lon, focus.lat],
      zoom: focus.zoom ?? Math.max(map.getZoom(), 16),
    });
  }, [map, focus]);

  useEffect(() => {
    if (!map || !pulseKey) return;
    return startPulse(map);
  }, [map, pulseKey]);

  if (!supported) return null;

  return (
    <div
      className={cn(
        styles.MapView,
        scheme === "dark" && styles.dark,
        className,
      )}
    >
      <div ref={container} className={styles.Canvas} />
      <div className={styles.Overlay}>{children}</div>
    </div>
  );
};

export default MapViewComponent;
