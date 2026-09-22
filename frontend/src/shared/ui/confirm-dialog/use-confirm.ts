import { useState } from "react";

/**
 * Состояние подтверждающего диалога. `target` - то, о чём спрашиваем, он же
 * отвечает, открыт ли диалог: `useConfirm<Residency>()` для «отвязать этот
 * дом», `useConfirm()` для действия без предмета.
 */
export const useConfirm = <T = void>() => {
  const [target, setTarget] = useState<{ value: T } | null>(null);

  return {
    target: target?.value,
    isOpen: target !== null,
    ask: (value: T) => setTarget({ value }),
    dismiss: () => setTarget(null),
  };
};
