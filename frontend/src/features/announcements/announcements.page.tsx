import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";

import { Card } from "@/shared/ui/card";
import { Disclosure } from "@/shared/ui/disclosure";
import { alertIcon, megaphoneIcon, wrenchIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { entrancesLabel } from "./scope";
import { useAnnouncements } from "./use-announcements";
import { announcementWhen } from "./when";
import { WorksDetails } from "./works";

import styles from "./announcements.module.css";

import type { components } from "@/shared/api/schema/generated";

type Announcement = components["schemas"]["AnnouncementItem"];

const AnnouncementCard = ({ item }: { item: Announcement }) => (
  <Card>
    <Flex align="center" gap={12}>
      <IconTile
        icon={item.urgent ? alertIcon : item.works ? wrenchIcon : megaphoneIcon}
        tone={item.urgent ? "negative" : "themed"}
      />

      <Flex className={styles.Grow} align="stretch" direction="column" gapY={2}>
        <Typography.Text variant="body-strong" color="primary">
          {item.urgent
            ? "Срочное объявление"
            : item.works
              ? "Плановые работы"
              : "Объявление"}
        </Typography.Text>

        <Typography.Text variant="description" color="tertiary">
          {[
            item.org_name,
            item.entrances && entrancesLabel(item.entrances),
            item.flats_count && "Для вашей квартиры",
            announcementWhen(item.created_at),
          ]
            .filter(Boolean)
            .join(" · ")}
        </Typography.Text>
      </Flex>
    </Flex>

    <Typography.Text className={styles.Text} variant="body" color="primary">
      {item.text.split(/(https?:\/\/[^\s]*[^\s.,;:!?)»])/).map((part, index) =>
        index % 2 === 1 ? (
          <a key={index} href={part} target="_blank" rel="noreferrer">
            {part}
          </a>
        ) : (
          part
        ),
      )}
    </Typography.Text>

    <WorksDetails announcement={item} />
  </Card>
);

const MoreButton = ({
  loading,
  onClick,
}: {
  loading: boolean;
  onClick: () => void;
}) => (
  <Button
    size="medium"
    variant="secondary"
    stretched
    loading={loading}
    onClick={onClick}
  >
    Показать ещё
  </Button>
);

const ArchivedAnnouncements = () => {
  const archive = useAnnouncements(true);

  if (archive.isPending) {
    return <LoadingState title="Загружаем архив" />;
  }

  if (archive.isError) {
    return <ErrorState error={archive.error} onRetry={archive.retry} />;
  }

  return (
    <Flex align="stretch" direction="column" gap={8}>
      {archive.items.map((item) => (
        <AnnouncementCard key={item.id} item={item} />
      ))}

      {archive.hasMore && (
        <MoreButton
          loading={archive.isLoadingMore}
          onClick={archive.loadMore}
        />
      )}
    </Flex>
  );
};

const AnnouncementsPage = () => {
  const {
    items,
    archiveTotal,
    isPending,
    isError,
    error,
    hasMore,
    isLoadingMore,
    retry,
    loadMore,
  } = useAnnouncements(false);

  const content = () => {
    if (isPending) {
      return <LoadingState fill title="Загружаем объявления" />;
    }

    if (isError) {
      return <ErrorState error={error} fill onRetry={retry} />;
    }

    if (items.length === 0 && archiveTotal === 0) {
      return (
        <EmptyState
          fill
          icon={megaphoneIcon}
          title="Объявлений пока нет"
          description="Здесь появятся объявления управляющей компании: отключения воды и света, ремонт, уборка"
        />
      );
    }

    return (
      <>
        {items.map((item) => (
          <AnnouncementCard key={item.id} item={item} />
        ))}

        {hasMore && <MoreButton loading={isLoadingMore} onClick={loadMore} />}

        {archiveTotal > 0 && (
          <Disclosure title={`Архив (${archiveTotal})`}>
            <ArchivedAnnouncements />
          </Disclosure>
        )}
      </>
    );
  };

  return (
    <Panel className={styles.Page} mode="secondary">
      {content()}
    </Panel>
  );
};

export const Component = AnnouncementsPage;
