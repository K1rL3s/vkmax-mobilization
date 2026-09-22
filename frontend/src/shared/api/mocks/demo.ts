import { ok, route } from "./reply";
import { activateDemoAccess, residencySummary } from "./state";

export const demoConfigs = [
  {
    path: "/demo/activate" as const,
    method: "post" as const,
    routes: [
      route(() => {
        const access = activateDemoAccess();

        return ok({
          org: access.org,
          residency: residencySummary(access.residency),
        });
      }),
    ],
  },
];
