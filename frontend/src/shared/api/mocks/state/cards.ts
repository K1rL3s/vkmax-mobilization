import type { components } from "../../schema/generated";

import {
  address,
  addressOf,
  demandTotal,
  isDemandSent,
  type MockFlat,
  type MockHouse,
} from "./houses";
import { flatMeters } from "./meters";
import {
  latestVerification,
  residencies,
  residencyForHouse,
  residencySummary,
  type MockResidency,
} from "./profile";

type Schemas = components["schemas"];

export const houseCard = (house: MockHouse): Schemas["HouseCard"] => {
  const residency = residencyForHouse(house.id);

  return {
    id: house.id,
    address: address(house),
    region: house.region,
    city: house.city,
    street: house.street,
    building: house.building,
    cadastral_no: house.cadastral_no,
    entrances: house.entrances,
    is_connected: house.is_connected,
    demand_count: demandTotal(house.id),
    demand_sent: isDemandSent(house.id),
    built_year: house.built_year,
    floors: house.floors,
    area: house.area,
    lat: house.lat,
    lon: house.lon,
    org: house.org,
    my_residency: residency ? residencySummary(residency) : null,
    chat_binding_code: null,
    chat_bound: false,
    overhaul: null,
    documents: [],
    org_stats: house.is_connected
      ? {
          closed: 38,
          on_time: 23,
          on_time_share: 6053,
          accept_time: 43,
          accept_time_median: 25,
          rating: 450,
          ratings_count: 22,
        }
      : null,
  };
};

export const flatCard = (
  flat: MockFlat,
  residency: MockResidency,
): Schemas["FlatCard"] => {
  const canSeeCharges = residency.role === "owner";

  return {
    id: flat.id,
    house_id: flat.house_id,
    address: addressOf(flat.house_id),
    number: flat.number,
    role: residency.role,
    verified: residency.verified,
    can_see_charges: canSeeCharges,
    can_vote: canSeeCharges,
    meters_count: flatMeters(flat.id).length,
    residents_count: residencies().filter((item) => item.flat_id === flat.id)
      .length,
    entrance: flat.entrance,
    area: flat.area,
    account_no:
      residency.verified && canSeeCharges ? flat.account_no.slice(-4) : null,
    verification_status: latestVerification(flat.id)?.status ?? null,
  };
};
