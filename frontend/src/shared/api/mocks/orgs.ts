import type { components } from "../schema/generated";

import { conflict, endpoint, forbidden, notFound, ok } from "./reply";
import { houseListItem, joinOrg, orgHouses, ZHILSERVIS } from "./state";

type Schemas = components["schemas"];

const REGISTRY = [
  { inn: "1655000001", registered: true, ...ZHILSERVIS },
  {
    inn: "1655000002",
    registered: false,
    id: 2,
    name: "ООО «УК Ленинская»",
    phone: "+7 843 200-40-40",
    address: "Казань, ул. Ленина, 2",
    license_no: "16-000456",
  },
];

export const orgsConfigs = [
  endpoint("post", "/orgs/lookup", (request) => {
    const org = REGISTRY.find((item) => item.inn === request.body.inn);

    return ok({
      found: org !== undefined,
      already_registered: org?.registered ?? false,
      name: org?.name ?? null,
      inn: org?.inn ?? null,
      license_no: org?.license_no ?? null,
      phone: org?.phone ?? null,
      address: org?.address ?? null,
      houses: org ? orgHouses(org.id).map(houseListItem) : [],
    } satisfies Schemas["OrgLookupResponse"]);
  }),
  endpoint("post", "/orgs", (request) => {
    const body = request.body as Schemas["RegisterOrgRequest"];
    const org = REGISTRY.find((item) => item.inn === body.inn);

    if (body.deeplink_code !== "demo") {
      return forbidden("Неверный код регистрации организации");
    }

    if (!org) {
      return notFound("Организация не найдена в реестре");
    }

    if (org.registered) {
      return conflict("Организация уже зарегистрирована");
    }

    org.registered = true;
    joinOrg({
      org_id: org.id,
      name: org.name,
      role: "creator",
      is_demo: false,
    });

    return ok({
      id: org.id,
      name: org.name,
      inn: org.inn,
      license_no: org.license_no ?? null,
      phone: org.phone,
      address: org.address,
      reception_note: null,
      registered_at: new Date().toISOString(),
      is_demo: false,
      houses_count: orgHouses(org.id).length,
      members_count: 1,
    } satisfies Schemas["OrgCard"]);
  }),
];
