import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";

import { rqClient } from "@/shared/api/instance";
import { houseParams } from "@/shared/model/session";
import { Card } from "@/shared/ui/card";
import { alertIcon, megaphoneIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { newsWhen } from "./when";

import styles from "./news.module.css";

const NewsPage = () => {
  const news = rqClient.useInfiniteQuery(
    "get",
    "/api/announcements",
    { params: { ...houseParams(), query: { limit: 20 } } },
    {
      pageParamName: "offset",
      initialPageParam: 0,
      getNextPageParam: (last, pages) => {
        const loaded = pages.reduce((sum, page) => sum + page.items.length, 0);

        return loaded < last.total ? loaded : undefined;
      },
    },
  );

  const content = () => {
    if (news.isPending) {
      return <LoadingState fill title="Загружаем новости" />;
    }

    if (news.isError) {
      return <ErrorState fill onRetry={() => void news.refetch()} />;
    }

    const items = news.data.pages.flatMap((page) => page.items);

    if (items.length === 0) {
      return (
        <EmptyState
          fill
          icon={megaphoneIcon}
          title="Новостей пока нет"
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
                <Typography.Text variant="body-strong" color="primary">
                  {item.urgent ? "Срочное объявление" : "Объявление УК"}
                </Typography.Text>
                <Typography.Text variant="description" color="secondary">
                  {newsWhen(item.created_at)}
                </Typography.Text>
              </Flex>
            </Flex>
            <Typography.Text
              variant="body"
              color="primary"
              className={styles.Text}
            >
              {item.text}
            </Typography.Text>
          </Card>
        ))}

        {news.hasNextPage && (
          <Button
            size="medium"
            variant="secondary"
            stretched
            loading={news.isFetchingNextPage}
            onClick={() => void news.fetchNextPage()}
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

export const Component = NewsPage;
