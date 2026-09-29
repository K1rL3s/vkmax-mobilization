import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { useOrgHouses } from "./model/use-access";
import { useIsOrgAdmin } from "./model/use-reception";
import { AccessForm } from "./ui/access-form";

const AdminAccessNewPage = () => {
  const canCreate = useIsOrgAdmin();
  const houses = useOrgHouses(canCreate);

  if (!canCreate) {
    return (
      <EmptyState
        fill
        title="Запросить доступ может администратор"
        description="Запрос доступа создаёт администратор организации: список квартир дома открыт только ему. Попросите его создать запрос - жителям придёт уведомление"
      />
    );
  }

  if (houses.isPending) {
    return <LoadingState fill title="Загружаем дома" />;
  }

  if (houses.isLoadingError) {
    return (
      <ErrorState
        error={houses.error}
        fill
        description="Не получилось загрузить дома организации"
        onRetry={() => void houses.refetch()}
      />
    );
  }

  if (houses.data.items.length === 0) {
    return (
      <EmptyState
        fill
        title="Запрашивать доступ негде"
        description="Запрос создаётся по дому организации, а домов у неё пока нет"
      />
    );
  }

  return <AccessForm houses={houses.data.items} />;
};

export const Component = AdminAccessNewPage;
