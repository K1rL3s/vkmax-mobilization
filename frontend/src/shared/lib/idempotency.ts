import { useState } from "react";

export const useIdempotencyKey = () => {
  const [key, setKey] = useState(() => crypto.randomUUID());

  return { key, renew: () => setKey(crypto.randomUUID()) };
};
