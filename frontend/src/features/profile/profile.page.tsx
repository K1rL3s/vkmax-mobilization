import { Button } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { EmptyState } from "@/shared/ui/state";
import { navProfileIcon } from "@/shared/ui/icon";

const ProfilePage = () => {
  return (
    <EmptyState
      fill
      icon={navProfileIcon}
      title="Профиль в разработке"
      description="Экран ещё делается. Скоро здесь появятся карточка дома и настройки уведомлений."
      action={
        <Button asChild size="medium" variant="secondary">
          <Link to={Routes.FLAT}>Моя квартира</Link>
        </Button>
      }
    />
  );
};

export const Component = ProfilePage;
