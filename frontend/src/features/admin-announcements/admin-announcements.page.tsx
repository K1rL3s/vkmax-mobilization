import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { useIsOrgAdmin } from "@/features/admin-reception";
import { Routes } from "@/shared/model/routes";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import { FilterChip } from "@/shared/ui/filter-chip";
import { Icon, megaphoneIcon, plusIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import {
  useAnnouncementList,
  useFinishWorks,
  useSentOutcome,
} from "./model/use-announcements";
import { AnnouncementRow } from "./ui/announcement-row";
import { SentNotice } from "./ui/sent-notice";

import styles from "./admin-announcements.module.css";

const NewAnnouncementButton = () => (
  <Button asChild size="medium" iconBefore={<Icon src={plusIcon} />}>
    <Link to={Routes.ADMIN_ANNOUNCEMENT_NEW}>Новое объявление</Link>
  </Button>
);

const AdminAnnouncementsPage = () => {
  const list = useAnnouncementList();
  const outcome = useSentOutcome();
  const isAdmin = useIsOrgAdmin();
  const finish = useFinishWorks();

  const content = () => {
    if (list.isPending) {
      return <LoadingState fill title="Загружаем объявления" />;
    }

    if (list.isError) {
      return <ErrorState error={list.loadError} fill onRetry={list.retry} />;
    }

    if (list.items.length === 0 && list.houseId) {
      return (
        <EmptyState
          fill
          icon={megaphoneIcon}
          title="По этому дому объявлений нет"
          description="Снимите фильтр по дому, чтобы увидеть все рассылки"
        />
      );
    }

    if (list.items.length === 0) {
      return (
        <EmptyState
          fill
          icon={megaphoneIcon}
          title="Объявлений пока нет"
          description="Объявление разом доходит до жителей выбранных домов: в чат дома и, если нужно, в личные сообщения. Сообщайте так об отключениях, ремонте и уборке"
          action={<NewAnnouncementButton />}
        />
      );
    }

    return (
      <>
        <NewAnnouncementButton />

        {list.items.map((announcement) => (
          <AnnouncementRow
            key={announcement.id}
            announcement={announcement}
            houses={list.houses}
            withRegister={isAdmin}
            onFinish={() => finish.ask(announcement)}
          />
        ))}

        {list.hasMore && (
          <Button
            size="medium"
            variant="secondary"
            stretched
            loading={list.isLoadingMore}
            onClick={list.loadMore}
          >
            Показать ещё
          </Button>
        )}
      </>
    );
  };

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex align="stretch" direction="column" gapY={4}>
        <Typography.Text asChild variant="title" color="primary">
          <h1>Объявления</h1>
        </Typography.Text>

        <Typography.Text variant="description" color="secondary">
          Рассылки жителям домов организации
        </Typography.Text>
      </Flex>

      {list.houseId && (
        <FilterChip onRemove={list.clearHouse}>
          Дом: {list.houseAddress ?? "выбран на карте"}
        </FilterChip>
      )}

      {outcome.sent && (
        <SentNotice sent={outcome.sent} onClose={outcome.dismiss} />
      )}

      {content()}

      <ConfirmDialog
        isOpen={finish.target !== undefined}
        title="Завершить работы досрочно?"
        description="Окончанием работ станет текущее время. Жители получат без звука «Работы завершены» туда же, куда ушло объявление, а предупреждение в форме заявки пропадёт"
        confirmLabel="Завершить"
        confirmVariant="primary"
        error={finish.error}
        isPending={finish.isPending}
        onConfirm={finish.confirm}
        onClose={finish.dismiss}
      />
    </Panel>
  );
};

export const Component = AdminAnnouncementsPage;
