import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { useSession, type Residency } from "@/shared/model/session";

export const useResidencySwitcher = () => {
  const navigate = useNavigate();
  const { residencies, currentResidency, select } = useSession();
  const [markedId, setMarkedId] = useState<number | null>(null);
  const [isSwitching, setSwitching] = useState(false);

  // отметка живёт только на этом экране: пока житель не нажал «Подтвердить»,
  // кабинет показывает прежний адрес
  const marked =
    residencies.find((item) => item.resident_id === markedId) ??
    currentResidency;

  return {
    residencies,
    marked,
    isSwitching,
    isMarked: (residency: Residency) =>
      residency.resident_id === marked?.resident_id,
    mark: (residency: Residency) => setMarkedId(residency.resident_id),
    confirm: async () => {
      setSwitching(true);

      if (marked && marked.resident_id !== currentResidency?.resident_id) {
        await select(marked.resident_id);
      }

      await navigate(Routes.HOME);
    },
  };
};
