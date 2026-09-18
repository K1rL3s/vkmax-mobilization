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

export const isConflict = (error: unknown): boolean => {
  if (!isApiError(error)) {
    return false;
  }

  return error.status === 409;
};
