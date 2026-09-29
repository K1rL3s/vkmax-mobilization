import { Suspense, useState } from "react";
import { Button, IconButton, Typography } from "@maxhub/max-ui";

import type { components } from "@/shared/api/schema/generated";
import { Autocomplete } from "@/shared/ui/autocomplete";
import {
  geoPinIcon,
  Icon,
  layersIcon,
  locateIcon,
  searchOutlineIcon,
} from "@/shared/ui/icon";
import {
  hasWebGL,
  MapSettingsSheet,
  MapView,
  useMapSettings,
} from "@/shared/ui/map";
import { EmptyState, LoadingState } from "@/shared/ui/state";

import { CITIES, CITY_ZOOM } from "./domain/cities";
import { useAddressSearch } from "./model/use-address-search";
import { usePointPick } from "./model/use-point-pick";
import { usePublicMap } from "./model/use-public-map";
import { HouseSheet } from "./ui/house-sheet";
import { MapFilters } from "./ui/map-filters";

import styles from "./public-house-map.module.css";

type House = components["schemas"]["HouseListItem"];

export type PublicHouseMapProps = {
  onPick?: (house: House) => void;
  onUnavailable?: () => void;
  initialFocus?: { lat: number; lon: number; zoom?: number };
  homeId?: number;
};

export const PublicHouseMap = ({
  onPick,
  onUnavailable,
  initialFocus = { ...CITIES[0], zoom: CITY_ZOOM },
  homeId,
}: PublicHouseMapProps) => {
  const [isUnavailable, setUnavailable] = useState(() => !hasWebGL());
  const [isLayersOpen, setLayersOpen] = useState(false);
  const [settings, setSettings] = useMapSettings();
  const map = usePublicMap();
  const pick = usePointPick(onPick);
  const search = useAddressSearch((house) => {
    pick.pickHouse(house.id);
    if (house.lat != null && house.lon != null) {
      map.flyTo({ lat: house.lat, lon: house.lon, zoom: 17 });
    }
  });

  if (isUnavailable) {
    return (
      <div className={styles.Root}>
        <EmptyState
          fill
          icon={geoPinIcon}
          title="Карта не загрузилась"
          description={
            onUnavailable
              ? "Найдите дом по адресу в списке"
              : "Проверьте связь и попробуйте позже"
          }
          action={
            onUnavailable && (
              <Button size="medium" variant="secondary" onClick={onUnavailable}>
                Выбрать списком
              </Button>
            )
          }
        />
      </div>
    );
  }

  return (
    <div className={styles.Root}>
      <div className={styles.Cities}>
        {CITIES.map((city) => (
          <Button
            key={city.name}
            size="small"
            variant="secondary"
            className={styles.Chip}
            onClick={() => map.flyTo({ ...city, zoom: CITY_ZOOM })}
          >
            {city.name}
          </Button>
        ))}
      </div>

      <Suspense fallback={<LoadingState fill title="Загружаем карту" />}>
        <MapView
          className={styles.Map}
          settings={settings}
          points={map.points}
          selectedId={pick.selectedId ?? homeId}
          highlight={pick.highlight}
          initialView={initialFocus}
          focus={map.focus}
          onPointClick={(id, stack) => {
            if (stack.length > 1) {
              pick.pickStack(
                map.houses.filter((house) => stack.includes(house.id)),
              );
            } else {
              pick.pickHouse(id);
            }
            const point = map.points.find((house) => house.id === id);
            if (point) map.flyTo({ lat: point.lat, lon: point.lon });
          }}
          onMapClick={(click) => {
            if (map.isZoomedOut) pick.close();
            else pick.pickSpot(click);
            map.flyTo({ lat: click.lat, lon: click.lon });
          }}
          onViewChange={map.changeView}
          onUnavailable={() => setUnavailable(true)}
        >
          <div className={styles.Search}>
            <Autocomplete
              placeholder="Улица и номер дома"
              icon={searchOutlineIcon}
              value={search.query}
              onChange={search.change}
              options={search.options}
              onSelect={search.select}
              status={search.status}
              onRetry={search.retry}
              loadingText="Ищем адреса…"
              emptyDescription="Проверьте название улицы или попробуйте ввести только её часть"
            />
          </div>

          {map.isLocateFailed && (
            <Typography.Text variant="description" className={styles.Note}>
              Не получилось определить, где вы. Выберите город
            </Typography.Text>
          )}

          <div className={styles.Bottom}>
            <div className={styles.Tools}>
              <IconButton
                size="medium"
                variant="secondary"
                aria-label="Слои"
                className={styles.Tool}
                onClick={() => setLayersOpen(true)}
              >
                <Icon src={layersIcon} size={22} />
              </IconButton>
              <IconButton
                size="medium"
                variant="secondary"
                aria-label="Где я"
                className={styles.Tool}
                loading={map.isLocating}
                onClick={map.locate}
              >
                <Icon src={locateIcon} size={22} />
              </IconButton>
            </div>

            {pick.place ? (
              <HouseSheet
                place={pick.place}
                canPick={onPick !== undefined}
                isAdding={pick.isAdding}
                addError={pick.addError}
                onChoose={pick.choose}
                onPickHouse={pick.pickHouse}
                onAdd={pick.addHouse}
                onClose={pick.close}
              />
            ) : map.isError ? (
              <div className={styles.Total}>
                <Typography.Text variant="body" color="primary">
                  Дома не загрузились
                </Typography.Text>
                <Button size="small" variant="ghost" onClick={map.retry}>
                  Повторить
                </Button>
              </div>
            ) : (
              map.hasFilters && (
                <div className={styles.Total}>
                  <Typography.Text variant="body" color="primary">
                    Включены фильтры
                  </Typography.Text>
                  <Button
                    size="small"
                    variant="ghost"
                    onClick={map.resetFilters}
                  >
                    Сбросить
                  </Button>
                </div>
              )
            )}
          </div>
        </MapView>

        <MapSettingsSheet
          open={isLayersOpen}
          onClose={() => setLayersOpen(false)}
          settings={settings}
          onChange={setSettings}
        >
          <MapFilters
            kind={map.kind}
            org={map.org}
            orgs={map.orgs}
            onKindChange={map.changeKind}
            onOrgToggle={map.toggleOrg}
          />
        </MapSettingsSheet>
      </Suspense>
    </div>
  );
};
