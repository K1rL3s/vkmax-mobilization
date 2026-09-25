export * from "./cards";
export * from "./demand";
export * from "./files";
export * from "./houses";
export * from "./http";
export * from "./meters";
export * from "./polls";
export * from "./profile";
export * from "./reception-access";
export * from "./reception-appointments";
export * from "./reception-hours";
export * from "./reception-time";
export * from "./requests";

import { resetDemand } from "./demand";
import { resetFiles } from "./files";
import { resetMeters } from "./meters";
import { resetPolls } from "./polls";
import { resetProfile } from "./profile";
import { resetReceptionAccess } from "./reception-access";
import { resetReceptionAppointments } from "./reception-appointments";
import { resetReceptionHours } from "./reception-hours";
import { resetRequests } from "./requests";

// состояние разложено по предметам, и сброс - функция на модуль: забытая
// строка видна на первом же демо, а общий объект возвращал бы ровно то, от
// чего уходим. Новый предмет состояния - модуль плюс строка в этом списке
const resets = [
  resetProfile,
  resetFiles,
  resetRequests,
  resetDemand,
  resetMeters,
  resetPolls,
  resetReceptionHours,
  resetReceptionAppointments,
  resetReceptionAccess,
];

export const resetState = (): void => {
  for (const reset of resets) {
    reset();
  }
};
