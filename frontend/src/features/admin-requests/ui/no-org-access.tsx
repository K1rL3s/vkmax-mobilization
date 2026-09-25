import { buildingIcon } from "@/shared/ui/icon";
import { EmptyState } from "@/shared/ui/state";

export const NoOrgAccess = () => (
  <EmptyState
    fill
    icon={buildingIcon}
    title="Нет доступа к организации"
    description="Похоже, вас исключили из неё или роль изменилась. Вернитесь в кабинет жителя или попросите руководителя открыть доступ."
  />
);
