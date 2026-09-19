import { EmptyState } from "@/shared/ui/state";
import { wrenchIcon } from "@/shared/ui/icon";

const RequestsPage = () => {
  return (
    <EmptyState
      fill
      icon={wrenchIcon}
      title="Заявки в разработке"
      description="Экран ещё делается. Скоро здесь появятся ваши заявки в управляющую компанию и кнопка «Новая заявка»."
    />
  );
};

export const Component = RequestsPage;
