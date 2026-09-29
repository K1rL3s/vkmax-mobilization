import { Navigate } from "react-router-dom";

import { useHouseCard } from "@/features/house";
import { Routes } from "@/shared/model/routes";
import { useSession } from "@/shared/model/session";
import { ErrorState, LoadingState } from "@/shared/ui/state";

import { PublicHouseMap } from "./public-house-map";

import styles from "./house-map.module.css";

const HouseMapPage = () => {
  const { currentResidency: residency } = useSession();
  const card = useHouseCard(residency?.house_id);

  if (!residency) {
    return <Navigate to={Routes.HOME} replace />;
  }

  if (card.isPending) {
    return <LoadingState fill title="Загружаем карту" />;
  }

  if (card.isError) {
    return (
      <ErrorState error={card.error} fill onRetry={() => void card.refetch()} />
    );
  }

  const { lat, lon } = card.data;

  return (
    <div className={styles.Page}>
      <PublicHouseMap
        initialFocus={
          lat != null && lon != null ? { lat, lon, zoom: 16 } : undefined
        }
        homeId={residency.house_id}
      />
    </div>
  );
};

export const Component = HouseMapPage;
