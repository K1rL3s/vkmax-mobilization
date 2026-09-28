import { Suspense, useMemo, useState } from "react";
import { Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { Chevron } from "@/shared/ui/chevron";
import { hasWebGL, MapView, useMapSettings } from "@/shared/ui/map";

import styles from "./house-map-preview.module.css";

export type HouseMapPreviewProps = { lat: number; lon: number };

export const HouseMapPreview = ({ lat, lon }: HouseMapPreviewProps) => {
  const [isAvailable, setAvailable] = useState(hasWebGL);
  const [settings] = useMapSettings();
  const points = useMemo(
    () => [{ id: 0, lat, lon, tone: "brand" as const }],
    [lat, lon],
  );

  if (!isAvailable) {
    return null;
  }

  return (
    <div className={styles.Preview}>
      <Suspense fallback={<div className={styles.Map} />}>
        <MapView
          className={styles.Map}
          settings={settings}
          points={points}
          initialView={{ lat, lon, zoom: 15 }}
          interactive={false}
          onUnavailable={() => setAvailable(false)}
        />
      </Suspense>
      <Link to={Routes.HOUSE_MAP} className={styles.Caption}>
        <Typography.Text variant="body-strong" color="primary">
          Соседние дома на карте
        </Typography.Text>
        <Chevron />
      </Link>
    </div>
  );
};
