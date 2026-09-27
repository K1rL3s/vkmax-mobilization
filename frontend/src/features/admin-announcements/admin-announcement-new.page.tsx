import { Button } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { buildingIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { useOrgHouses } from "./model/use-announcements";
import { AnnouncementForm } from "./ui/announcement-form";

const AdminAnnouncementNewPage = () => {
  const houses = useOrgHouses();

  if (houses.isPending) {
    return <LoadingState fill title="Загружаем дома" />;
  }

  if (houses.isError) {
    return (
      <ErrorState
        error={houses.error}
        fill
        onRetry={() => void houses.refetch()}
      />
    );
  }

  if (houses.data.items.length === 0) {
    return (
      <EmptyState
        fill
        icon={buildingIcon}
        title="Объявлять пока некому"
        description="Объявление уходит жителям домов под управлением организации, а домов у неё пока нет. Список домов - на вкладке «Дома»"
        action={
          <Button asChild size="medium" variant="secondary">
            <Link to={Routes.ADMIN_HOUSES}>К домам</Link>
          </Button>
        }
      />
    );
  }

  return <AnnouncementForm houses={houses.data.items} />;
};

export const Component = AdminAnnouncementNewPage;
