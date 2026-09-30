import { z } from "zod";

import { Routes } from "@/shared/model/routes";
import type { Residency } from "@/shared/model/session";

const changeFlatState = z.object({
  house: z.object({ id: z.number().int(), address: z.string() }),
  returnTo: z.string().startsWith("/"),
});

export const changeFlatLink = (residency: Residency, returnTo: string) => ({
  to: `${Routes.ONBOARDING_HOUSE}?view=list`,
  state: {
    house: { id: residency.house_id, address: residency.address },
    returnTo,
  } satisfies z.infer<typeof changeFlatState>,
});

export const parseChangeFlat = (state: unknown) =>
  changeFlatState.safeParse(state).data ?? null;
