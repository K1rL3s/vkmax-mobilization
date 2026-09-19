import type { components } from "../schema/generated";

import type { MockHttpRequest } from "./state";

export type Reply = {
  status: number;
  body: unknown;
};

export const ok = (body: unknown): Reply => ({ status: 200, body });

export const fail = (status: number, title: string, detail: string): Reply => ({
  status,
  body: {
    status,
    ok: false,
    trace_id: "00000000-0000-4000-8000-000000000000",
    error: { title, detail },
  } satisfies components["schemas"]["ApiError_BaseError_"],
});

export const unauthorized = (): Reply =>
  fail(401, "Требуется авторизация", "Нет заголовка WebAppData");

export const notFound = (detail: string): Reply =>
  fail(404, "Сущность не найдена", detail);

export const badRequest = (detail: string): Reply =>
  fail(400, "Некорректный запрос", detail);

export const forbidden = (detail: string): Reply =>
  fail(403, "Недостаточно прав", detail);

export const conflict = (detail: string): Reply =>
  fail(409, "Конфликт состояния", detail);

type Handler = (request: MockHttpRequest) => Reply | Promise<Reply>;

// заголовок авторизации проверяется у каждой ручки: забытый WebAppData должен
// падать на моке так же, как упал бы на бекенде
export const route = (handler: Handler) => ({
  data: (request: unknown) => {
    const mockRequest = request as MockHttpRequest;

    return mockRequest.headers.webappdata
      ? handler(mockRequest)
      : unauthorized();
  },
  interceptors: {
    response: (
      data: unknown,
      params: { setStatusCode: (n: number) => void },
    ) => {
      const reply = data as Reply;
      params.setStatusCode(reply.status);

      return reply.body;
    },
  },
});

export const number = (value: string | undefined): number | null => {
  if (value === undefined || value.trim() === "") {
    return null;
  }

  const parsed = Number(value);

  return Number.isFinite(parsed) ? parsed : null;
};
