import { useState } from "react";

import { type HouseCard, useHouseCard } from "@/features/house";
import type { components } from "@/shared/api/schema/generated";
import { authParams, rqClient } from "@/shared/api/instance";
import type { MapClick } from "@/shared/ui/map";

type House = components["schemas"]["HouseListItem"];

type Spot = { lat: number; lon: number };

export type PickedPlace =
  | { kind: "loading" }
  | { kind: "error"; error: unknown; retry: () => void }
  | { kind: "house"; house: HouseCard }
  | { kind: "address"; address: string }
  | { kind: "geocoder_failed" }
  | { kind: "nothing" };

export const usePointPick = (onPick?: (house: House) => void) => {
  const [houseId, setHouseId] = useState<number | null>(null);
  const [spot, setSpot] = useState<Spot | null>(null);
  const [highlight, setHighlight] = useState<GeoJSON.Geometry | null>(null);

  const at = rqClient.useQuery(
    "get",
    "/api/houses/at",
    { params: { ...authParams(), query: spot ?? { lat: 0, lon: 0 } } },
    { enabled: spot !== null, retry: false, staleTime: Infinity },
  );
  const add = rqClient.useMutation("post", "/api/houses", {
    onSuccess: (house) => onPick?.(house),
  });

  const selectedId = spot ? (at.data?.house?.id ?? null) : houseId;
  const card = useHouseCard(selectedId ?? undefined);

  const place = (): PickedPlace | null => {
    if (spot) {
      if (at.isPending) return { kind: "loading" };
      if (at.isError) {
        return {
          kind: "error",
          error: at.error,
          retry: () => void at.refetch(),
        };
      }
      if (at.data.address) {
        return { kind: "address", address: at.data.address.address };
      }
      if (at.data.geocoder_failed) return { kind: "geocoder_failed" };
      if (!at.data.house) return { kind: "nothing" };
    } else if (houseId === null) {
      return null;
    }

    if (card.isPending) return { kind: "loading" };
    if (card.isError) {
      return {
        kind: "error",
        error: card.error,
        retry: () => void card.refetch(),
      };
    }
    return { kind: "house", house: card.data };
  };

  return {
    selectedId,
    highlight,
    place: place(),
    pickHouse: (id: number) => {
      add.reset();
      setSpot(null);
      setHighlight(null);
      setHouseId(id);
    },
    pickSpot: (click: MapClick) => {
      add.reset();
      setHouseId(null);
      setSpot({ lat: click.lat, lon: click.lon });
      setHighlight(click.building);
    },
    close: () => {
      add.reset();
      setSpot(null);
      setHighlight(null);
      setHouseId(null);
    },
    choose: (house: HouseCard) =>
      onPick?.({ ...house, org_name: house.org?.name }),
    addHouse: () => {
      if (spot) add.mutate({ params: authParams(), body: spot });
    },
    isAdding: add.isPending,
    addError: add.error,
  };
};
