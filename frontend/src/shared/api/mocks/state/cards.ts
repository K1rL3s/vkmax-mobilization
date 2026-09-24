import type { components } from "../../schema/generated";

type Schemas = components["schemas"];

import { demandSent, demandTotal } from "./demand";
import { address, findHouse, type MockFlat, type MockHouse } from "./houses";
import { flatMeters } from "./meters";
import {
  latestVerification,
  residencies,
  residencyForHouse,
  residencySummary,
  type MockResidency,
} from "./profile";

export const houseCard = (house: MockHouse): Schemas["HouseCard"] => ({
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
  demand_sent: demandSent(house.id),
  built_year: house.built_year,
  floors: house.floors,
  area: house.area,
  lat: house.lat,
  lon: house.lon,
  org: house.org,
  my_residency: (() => {
    const residency = residencyForHouse(house.id);

    return residency ? residencySummary(residency) : null;
  })(),
  chat_binding_code: null,
  chat_bound: false,
  overhaul: null,
  documents: [],
});

export const flatCard = (
  flat: MockFlat,
  residency: MockResidency,
): Schemas["FlatCard"] => {
  const house = findHouse(flat.house_id);
  const canSeeCharges = residency.role === "owner";

  return {
    id: flat.id,
    house_id: flat.house_id,
    address: house ? address(house) : "",
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
    // хвост лицевого счета видит только подтвержденный житель с доступом к
    // начислениям: арендатору счет не показывают вовсе
    account_no:
      residency.verified && canSeeCharges ? flat.account_no.slice(-4) : null,
    verification_status: latestVerification(flat.id)?.status ?? null,
  };
};
