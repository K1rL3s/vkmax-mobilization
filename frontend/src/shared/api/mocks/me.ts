import { badRequest, ok, route } from "./reply";
import { acceptConsent, me } from "./state";

const TRACKED_EVENTS = new Set(["miniapp_open", "announcement_click"]);

export const meConfigs = [
  {
    path: "/me" as const,
    method: "get" as const,
    routes: [route(() => ok(me()))],
  },
  {
    path: "/me/consent" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const version = request.body.version;

        if (typeof version !== "string" || version.trim() === "") {
          return badRequest("Укажите версию согласия");
        }

        acceptConsent(version);

        return ok(me());
      }),
    ],
  },
  {
    path: "/events" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const type = request.body.type;

        if (typeof type !== "string" || !TRACKED_EVENTS.has(type)) {
          return badRequest("Неизвестный тип события");
        }

        return ok({ ok: true });
      }),
    ],
  },
];
