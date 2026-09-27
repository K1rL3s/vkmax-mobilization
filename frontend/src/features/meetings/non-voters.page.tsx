import { Flex, Panel, Typography } from "@maxhub/max-ui";

import { checkIcon, pollIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { flatsCount } from "./domain/poll";
import { useNonVoters } from "./model/use-non-voters";

import styles from "./non-voters.module.css";

const NonVotersPage = () => {
  const view = useNonVoters();

  if (view.isPending) {
    return <LoadingState fill title="Загружаем квартиры" />;
  }

  if (view.isForbidden) {
    return (
      <EmptyState
        fill
        icon={pollIcon}
        title="Список закрыт"
        description="Непроголосовавшие квартиры видит организатор опроса или управляющая компания."
      />
    );
  }

  if (view.isError) {
    return <ErrorState error={view.loadError} fill onRetry={view.retry} />;
  }

  if (view.items.length === 0) {
    return (
      <EmptyState
        fill
        icon={checkIcon}
        title="Непроголосовавших нет"
        description="Все квартиры дома уже отдали голос."
      />
    );
  }

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex align="stretch" direction="column" gapY={4}>
        <Typography.Text asChild variant="title" color="primary">
          <h1>Не проголосовали</h1>
        </Typography.Text>

        <Typography.Text variant="description" color="secondary">
          {flatsCount(view.items.length)} из{" "}
          {view.totalFlats ?? view.items.length}
          {" · "}кто как проголосовал, не показывается
        </Typography.Text>
      </Flex>

      {view.groups.map((group) => (
        <Flex
          key={group.title}
          asChild
          align="stretch"
          direction="column"
          gapY={4}
        >
          <section>
            <Flex align="center" gap={8}>
              <Typography.Text
                asChild
                className={styles.Grow}
                variant="body-strong"
                color="primary"
              >
                <h2>{group.title}</h2>
              </Typography.Text>

              <Typography.Text variant="description" color="secondary">
                {flatsCount(group.flats.length)}
              </Typography.Text>
            </Flex>

            <div className={styles.Flats}>
              {group.flats.map((flat) => (
                <Typography.Text
                  key={flat.flat_id}
                  className={styles.Flat}
                  variant="body"
                  color="primary"
                >
                  {flat.flat_number}
                </Typography.Text>
              ))}
            </div>
          </section>
        </Flex>
      ))}
    </Panel>
  );
};

export const Component = NonVotersPage;
