import type { RestMethod } from "mock-config-server";

import type { components } from "../schema/generated";

import { residencies } from "./state";

export type MockHttpRequest = AsyncIterable<Uint8Array> & {
  params: Record<string, string>;
  query: Record<string, string | undefined>;
  body: Record<string, unknown>;
  headers: Record<string, string | undefined>;
};

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

export const notFound = (detail: string): Reply =>
  fail(404, "Сущность не найдена", detail);

export const badRequest = (detail: string): Reply =>
  fail(400, "Некорректный запрос", detail);

export const forbidden = (detail: string): Reply =>
  fail(403, "Недостаточно прав", detail);

export const conflict = (detail: string): Reply =>
  fail(409, "Конфликт состояния", detail);

export const isReply = (value: unknown): value is Reply =>
  typeof value === "object" && value !== null && "status" in value;

export const endpoint = <Method extends RestMethod>(
  method: Method,
  path: `/${string}`,
  handler: (request: MockHttpRequest) => Reply | Promise<Reply>,
) => ({
  method,
  path,
  routes: [
    {
      data: (request: unknown) => {
        const mockRequest = request as MockHttpRequest;

        return mockRequest.headers.webappdata
          ? handler(mockRequest)
          : fail(401, "Требуется авторизация", "Нет заголовка WebAppData");
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
    },
  ],
});

export const number = (value: string | undefined): number | null => {
  if (value === undefined || value.trim() === "") {
    return null;
  }

  const parsed = Number(value);

  return Number.isFinite(parsed) ? parsed : null;
};

export const page = <T>(
  items: T[],
  query: MockHttpRequest["query"],
  limit = 20,
) => {
  const offset = number(query.offset) ?? 0;

  return {
    items: items.slice(offset, offset + (number(query.limit) ?? limit)),
    total: items.length,
  };
};

export const houseOf = (request: MockHttpRequest): number | null =>
  number(request.headers["x-house-id"]) ??
  residencies().at(-1)?.house_id ??
  null;
