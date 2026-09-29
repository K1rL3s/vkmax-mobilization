import { Suspense, useMemo, useState } from "react";
import { Button, Typography } from "@maxhub/max-ui";
import { useLocalStorage } from "@siberiacancode/reactuse";

import { cn } from "@/shared/lib/css";
import { plural } from "@/shared/lib/format";
import { geoPinIcon, Icon, layersIcon } from "@/shared/ui/icon";
import {
  hasWebGL,
  type MapBounds,
  type MapFocus,
  MapSettingsSheet,
  type MapTone,
  MapView,
  TONE_COLORS,
  useMapSettings,
} from "@/shared/ui/map";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { metersTone, residentsTone, STATES } from "../domain/map-filters";
import { type AdminMapModel, QUICK_FILTERS } from "../model/use-admin-map";
import { usePlatformMap } from "../model/use-platform-map";
import { HousePopup, PlatformHousePopup, StackPopup } from "./house-popup";
import { MapLayers } from "./map-layers";

import styles from "./houses-map.module.css";

const STATE_TONE = Object.fromEntries(
  STATES.map((state) => [state.id, state.tone]),
) as Record<(typeof STATES)[number]["id"], MapTone>;

const LEGENDS: Record<"meters" | "residents", [MapTone, string][]> = {
  meters: [
    ["green", "от 80%"],
    ["yellow", "50-80%"],
    ["red", "меньше 50%"],
    ["muted", "нет счётчиков"],
  ],
  residents: [
    ["green", "от 30% квартир"],
    ["yellow", "10-30%"],
    ["red", "меньше 10%"],
  ],
};

const Dot = ({ tone }: { tone: MapTone }) => (
  <span className={styles.Dot} style={{ backgroundColor: TONE_COLORS[tone] }} />
);

export const HousesMap = ({ map }: { map: AdminMapModel }) => {
  const { filters, houses, isAdmin, fitItems } = map;
  const [shared, setShared] = useMapSettings();
  const cluster = useLocalStorage<unknown>("zheka.admin-map.cluster", false);
  const settings = { ...shared, cluster: cluster.value === true };
  const [supported] = useState(hasWebGL);
  const [unavailable, setUnavailable] = useState(false);
  const [layersOpen, setLayersOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [stack, setStack] = useState<number[] | null>(null);
  const [bounds, setBounds] = useState<MapBounds | null>(null);
  const [zoom, setZoom] = useState<number | undefined>();
  const [focus, setFocus] = useState<MapFocus | null>(null);
  const platform = usePlatformMap(filters, bounds);
  const items = houses.data?.items;

  const points = useMemo(() => {
    const peak = Math.max(
      1,
      ...(items ?? []).map((house) => house.period_requests),
    );
    return (items ?? []).map((house) => ({
      id: house.id,
      lat: house.lat,
      lon: house.lon,
      tone:
        filters.color === "meters"
          ? metersTone(house.meters_percent)
          : filters.color === "residents"
            ? residentsTone(house.residents_count, house.flats_count)
            : STATE_TONE[house.state],
      size: house.open,
      weight: house.period_requests / peak,
      label: house.building,
    }));
  }, [items, filters.color]);

  const backgroundPoints = useMemo(
    () =>
      platform.items.map((house) => ({
        id: house.id,
        lat: house.lat,
        lon: house.lon,
        tone: (house.kind === "connected" ? "brand" : "muted") as MapTone,
      })),
    [platform.items],
  );

  const initialView = useMemo(() => {
    if (!fitItems || fitItems.length === 0) {
      return { lat: 55.7512, lon: 37.6184, zoom: 11 };
    }
    const lats = fitItems.map((house) => house.lat);
    const lons = fitItems.map((house) => house.lon);
    const lat = (Math.min(...lats) + Math.max(...lats)) / 2;
    const span = Math.max(
      Math.max(...lons) - Math.min(...lons),
      (Math.max(...lats) - Math.min(...lats)) / Math.cos((lat * Math.PI) / 180),
      0.001,
    );
    return {
      lat,
      lon: (Math.min(...lons) + Math.max(...lons)) / 2,
      zoom: Math.min(15, Math.max(10, Math.log2((280 * 360) / (512 * span)))),
    };
  }, [fitItems]);

  if (!supported || unavailable) {
    return (
      <div className={styles.Fallback}>
        <EmptyState
          fill
          icon={geoPinIcon}
          title="Карта не открылась"
          description="На этом устройстве карта не работает или не загрузилась. Дома можно посмотреть списком"
          action={
            <Button
              size="medium"
              variant="secondary"
              onClick={() => map.update({ view: "list" })}
            >
              Показать списком
            </Button>
          }
        />
      </div>
    );
  }

  if (houses.isPending || map.isFitting) {
    return <LoadingState fill title="Загружаем карту домов" />;
  }

  if (!houses.data) {
    return (
      <ErrorState
        error={houses.error}
        fill
        onRetry={() => void houses.refetch()}
      />
    );
  }

  const select = (id: number) => {
    setSelectedId(id);
    const house =
      items?.find((item) => item.id === id) ??
      platform.items.find((item) => item.id === id);
    if (!house || !bounds) return;
    const height = bounds.north - bounds.south;
    if (house.lat < bounds.south + height * 0.55) {
      setFocus({ lat: house.lat - height * 0.22, lon: house.lon, zoom });
    }
  };

  const stackHouses = [...(items ?? []), ...platform.items].filter((house) =>
    stack?.includes(house.id),
  );
  const selected = items?.find((house) => house.id === selectedId);
  const platformSelected = selected
    ? undefined
    : platform.items.find((house) => house.id === selectedId);
  const shown = houses.data.items.length;
  const legend = filters.color === "requests" ? null : LEGENDS[filters.color];

  return (
    <div className={styles.HousesMap}>
      <Suspense fallback={<LoadingState fill title="Загружаем карту" />}>
        <MapView
          className={styles.Map}
          settings={settings}
          points={points}
          backgroundPoints={backgroundPoints}
          heat={filters.heat}
          selectedId={selectedId}
          pulseIds={map.pulseIds}
          initialView={initialView}
          focus={focus}
          onPointClick={(id, ids) => {
            select(id);
            setStack(ids.length > 1 ? ids : null);
          }}
          onMapClick={() => {
            setSelectedId(null);
            setStack(null);
          }}
          onViewChange={(next, nextZoom) => {
            setBounds(next);
            setZoom(nextZoom);
          }}
          onUnavailable={() => setUnavailable(true)}
        >
          <div className={styles.Filters}>
            <div
              className={styles.Chips}
              role="group"
              aria-label="Состояние домов"
            >
              {STATES.map((state) => {
                const on = filters.states.includes(state.id);
                return (
                  <button
                    key={state.id}
                    type="button"
                    aria-pressed={on}
                    className={cn(styles.Chip, on && styles.on)}
                    onClick={() => map.toggle("states", state.id)}
                  >
                    {!legend && <Dot tone={state.tone} />}
                    {state.label}
                  </button>
                );
              })}
            </div>

            <div
              className={styles.Chips}
              role="group"
              aria-label="Быстрые фильтры"
            >
              {QUICK_FILTERS.filter((quick) => isAdmin || !quick.adminOnly).map(
                (quick) => {
                  const on = filters.quick.some((id) => id === quick.id);
                  return (
                    <button
                      key={quick.id}
                      type="button"
                      aria-pressed={on}
                      className={cn(styles.Chip, on && styles.on)}
                      onClick={() => map.toggle("quick", quick.id)}
                    >
                      {quick.label}
                    </button>
                  );
                },
              )}
            </div>
          </div>

          <button
            type="button"
            className={styles.Layers}
            aria-label="Слои и фильтры"
            onClick={() => setLayersOpen(true)}
          >
            <Icon src={layersIcon} size={24} />
          </button>

          {stackHouses.length > 1 ? (
            <StackPopup
              houses={stackHouses}
              onChoose={(id) => {
                setStack(null);
                select(id);
              }}
              onClose={() => {
                setStack(null);
                setSelectedId(null);
              }}
            />
          ) : selected ? (
            <HousePopup
              house={selected}
              isAdmin={isAdmin}
              onClose={() => setSelectedId(null)}
            />
          ) : platformSelected ? (
            <PlatformHousePopup
              house={platformSelected}
              onClose={() => setSelectedId(null)}
            />
          ) : (
            <div className={styles.Summary}>
              <Typography.Text variant="body-strong" color="primary">
                {plural(shown, ["Показан", "Показано", "Показано"])} {shown}{" "}
                {plural(shown, ["дом", "дома", "домов"])}
                {houses.data.without_coords > 0 &&
                  `, без координат: ${houses.data.without_coords}`}
              </Typography.Text>

              {filters.platform &&
                (platform.isError ? (
                  <Typography.Text variant="description" color="secondary">
                    Дома платформы не загрузились
                  </Typography.Text>
                ) : (
                  <div className={styles.Legend}>
                    {(
                      [
                        ["brand", "другие подключённые УК"],
                        ["muted", "не подключены"],
                      ] as const
                    ).map(([tone, label]) => (
                      <span key={tone} className={styles.LegendItem}>
                        <Dot tone={tone} />
                        <Typography.Text
                          variant="description"
                          color="secondary"
                        >
                          {label}
                        </Typography.Text>
                      </span>
                    ))}
                  </div>
                ))}

              {legend && (
                <div className={styles.Legend}>
                  {legend.map(([tone, label]) => (
                    <span key={tone} className={styles.LegendItem}>
                      <Dot tone={tone} />
                      <Typography.Text variant="description" color="secondary">
                        {label}
                      </Typography.Text>
                    </span>
                  ))}
                </div>
              )}

              {map.hasFilters && (
                <button
                  type="button"
                  className={styles.Reset}
                  onClick={map.reset}
                >
                  Сбросить
                </button>
              )}
            </div>
          )}
        </MapView>
      </Suspense>

      <MapSettingsSheet
        open={layersOpen}
        onClose={() => setLayersOpen(false)}
        settings={settings}
        onChange={({ cluster: next, ...rest }) => {
          setShared({ ...rest, cluster: shared.cluster });
          cluster.set(next);
        }}
        sizeOption
      >
        {layersOpen && <MapLayers map={map} orgs={platform.orgs} />}
      </MapSettingsSheet>
    </div>
  );
};
