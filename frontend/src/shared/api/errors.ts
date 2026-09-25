import type { components } from "./schema/generated";

const isApiError = (
  error: unknown,
): error is components["schemas"]["ApiError_BaseError_"] =>
  typeof error === "object" &&
  error !== null &&
  "status" in error &&
  typeof error.status === "number";

const hasStatus = (error: unknown, status: number): boolean =>
  isApiError(error) && error.status === status;

export const errorDetail = (error: unknown): string | undefined =>
  isApiError(error) ? error.error.detail : undefined;

export const isConflict = (error: unknown): boolean => hasStatus(error, 409);

export const isForbidden = (error: unknown): boolean => hasStatus(error, 403);

export const retryUnlessForbidden = (count: number, error: unknown) =>
  !isForbidden(error) && count < 3;
