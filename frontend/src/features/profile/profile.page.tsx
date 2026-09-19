import { EmptyState } from "@/shared/ui/state";
import { navProfileIcon } from "@/shared/ui/icon";

const ProfilePage = () => {
  return (
    <EmptyState
      fill
      icon={navProfileIcon}
      title="Профиль в разработке"
      description="Экран ещё делается. Скоро здесь появятся карточка дома, «Моя квартира» и настройки уведомлений."
    />
  );
};

export const Component = ProfilePage;
