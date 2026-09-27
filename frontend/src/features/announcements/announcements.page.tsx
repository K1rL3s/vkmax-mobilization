import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";

import { Card } from "@/shared/ui/card";
import { alertIcon, megaphoneIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { useAnnouncements } from "./use-announcements";
import { announcementWhen } from "./when";

import styles from "./announcements.module.css";

const AnnouncementsPage = () => {
  const {
    items,
    isPending,
    isError,
    error,
    hasMore,
    isLoadingMore,
    retry,
    loadMore,
  } = useAnnouncements();

  const content = () => {
    if (isPending) {
      return <LoadingState fill title="Загружаем объявления" />;
    }

    if (isError) {
      return <ErrorState error={error} fill onRetry={retry} />;
    }

    if (items.length === 0) {
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
          <Card key={item.id}>
            <Flex align="center" gap={12}>
              <IconTile
                icon={item.urgent ? alertIcon : megaphoneIcon}
                tone={item.urgent ? "negative" : "themed"}
              />

              <Flex
                className={styles.Grow}
                align="stretch"
                direction="column"
                gapY={2}
              >
                <Typography.Text variant="title" color="primary">
                  {item.urgent ? "Срочное объявление" : "Объявление"}
                </Typography.Text>

                <Typography.Text variant="description" color="tertiary">
                  {[item.org_name, announcementWhen(item.created_at)]
                    .filter(Boolean)
                    .join(" · ")}
                </Typography.Text>
              </Flex>
            </Flex>

            <Typography.Text
              className={styles.Text}
              variant="body"
              color="primary"
            >
              {item.text}
            </Typography.Text>
          </Card>
        ))}

        {hasMore && (
          <Button
            size="medium"
            variant="secondary"
            stretched
            loading={isLoadingMore}
            onClick={loadMore}
          >
            Показать ещё
          </Button>
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
