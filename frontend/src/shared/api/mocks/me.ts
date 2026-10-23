import type { components } from "../schema/generated";

import { badRequest, endpoint, ok } from "./reply";
import {
  acceptConsent,
  activateDemoAccess,
  forgetUser,
  me,
  user,
} from "./state";

type Schemas = components["schemas"];

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
    const body = request.body as Schemas["UpdateAppearanceRequest"];

    if (
      body.text_size &&
      !["normal", "large", "xlarge"].includes(body.text_size)
    ) {
      return badRequest("Неизвестный размер текста");
    }

    if (body.theme && !["system", "light", "dark"].includes(body.theme)) {
      return badRequest("Неизвестная тема");
    }

    user.text_size = body.text_size ?? user.text_size;
    user.theme = body.theme ?? user.theme;

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
  endpoint("delete", "/me", () => {
    forgetUser();

    return { status: 204, body: null };
  }),
];
