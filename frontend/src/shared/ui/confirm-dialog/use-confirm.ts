import { useState } from "react";

export const useConfirm = <T = void>() => {
  const [target, setTarget] = useState<{ value: T } | null>(null);

  return {
    target: target?.value,
    isOpen: target !== null,
    ask: (value: T) => setTarget({ value }),
    dismiss: () => setTarget(null),
  };
};
