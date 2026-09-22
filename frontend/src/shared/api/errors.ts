import type { components } from "./schema/generated";

type ApiError = components["schemas"]["ApiError_BaseError_"];

// openapi-fetch отдает разобранное тело, а не Response, поэтому статус
// смотрим в конверте ошибки - он одинаков у всех ручек контракта
const isApiError = (error: unknown): error is ApiError => {
  if (typeof error !== "object" || error === null) {
    return false;
  }

  if (!("status" in error)) {
    return false;
  }

  return typeof error.status === "number";
};

const hasStatus = (error: unknown, status: number): boolean =>
  isApiError(error) && error.status === status;

export const isConflict = (error: unknown): boolean => hasStatus(error, 409);

export const isForbidden = (error: unknown): boolean => hasStatus(error, 403);
