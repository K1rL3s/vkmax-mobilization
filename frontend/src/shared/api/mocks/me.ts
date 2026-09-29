import { badRequest, endpoint, ok } from "./reply";
import { acceptConsent, activateDemoAccess, me, user } from "./state";

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
  endpoint("post", "/me/phone", (request) => {
    const phone = request.body.phone;

    if (typeof phone !== "string" || phone.trim() === "") {
      return badRequest("Номер не подтвержден MAX, попробуйте еще раз");
    }

    user.phone = `+${phone.replace(/^\+/, "")}`;

    return ok(me());
  }),
  endpoint("delete", "/me/phone", () => {
    user.phone = null;

    return ok(me());
  }),
  endpoint("put", "/me/appearance", (request) => {
    const size = request.body.text_size;

    if (!["normal", "large", "xlarge"].includes(String(size))) {
      return badRequest("Неизвестный размер текста");
    }

    user.text_size = size as typeof user.text_size;

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
