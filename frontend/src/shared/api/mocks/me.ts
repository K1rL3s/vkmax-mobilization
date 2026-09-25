import { badRequest, endpoint, ok } from "./reply";
import { acceptConsent, activateDemoAccess, me } from "./state";

export const meConfigs = [
  endpoint("get", "/me", () => ok(me())),
  endpoint("post", "/me/consent", (request) => {
    const version = request.body.version;

    if (typeof version !== "string" || version.trim() === "") {
      return badRequest("Укажите версию согласия");
    }

    acceptConsent(version);

    return ok(me());
  }),
  endpoint("post", "/events", (request) => {
    const type = request.body.type;

    return typeof type === "string" &&
      ["miniapp_open", "announcement_click"].includes(type)
      ? ok({ ok: true })
      : badRequest("Неизвестный тип события");
  }),
  endpoint("post", "/demo/activate", () => ok(activateDemoAccess())),
];
