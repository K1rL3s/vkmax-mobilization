import type { RequestMessage } from "./types";

export const deliveryMark = ({
  delivery,
  read,
  created_at: createdAt,
}: RequestMessage) => {
  if (!delivery) {
    return null;
  }

  if (read) {
    return "read";
  }

  if (
    delivery === "pending" &&
    Date.now() - Date.parse(createdAt) >= 10 * 60 * 1000
  ) {
    return "unknown";
  }

  return delivery;
};
