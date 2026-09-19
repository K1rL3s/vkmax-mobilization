import { Flex, Typography } from "@maxhub/max-ui";

import { cn } from "@/shared/lib/css";
import { buildingIcon, Icon, userIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { ErrorState, LoadingState } from "@/shared/ui/state";

import { CATEGORY_ICON, ZONE_LABEL } from "./domain/category";
import { formatDay, formatTime, plural } from "./domain/format";
import { isFinished, STATUS_LABEL, STATUS_TONE } from "./domain/status";
import { useRequest } from "./model/use-request";
import { Answers } from "./ui/answers";
import { DeadlinePanel } from "./ui/deadline-panel";
import { RequestTimeline } from "./ui/request-timeline";

import styles from "./request.module.css";

const RequestPage = () => {
  const { request, zone, timeline, isPending, isError, retry } = useRequest();

  if (isPending) {
    return <LoadingState fill title="Загружаем заявку" />;
  }

  if (isError || !request) {
    return <ErrorState fill onRetry={retry} />;
  }

  const tone = STATUS_TONE[request.status];
  // срок идёт, пока заявка в работе: на приёмке и после неё считать нечего
  const isRunning =
    !isFinished(request.status) && request.status !== "on_review";

  return (
    <div className={styles.Page}>
      <Flex align="center" gap={12}>
        <IconTile
          icon={CATEGORY_ICON[request.category]}
          tone={tone}
          size="large"
        />
        <Flex
          className={styles.Grow}
          align="stretch"
          direction="column"
          gapY={2}
        >
          <Typography.Text variant="description" color="secondary">
            Заявка №{request.id}
          </Typography.Text>
          <Typography.Text variant="title" color="primary">
            {request.description}
          </Typography.Text>
          <Typography.Text variant="description" color="secondary">
            Подана {formatDay(request.created_at)} в{" "}
            {formatTime(request.created_at)}
            {request.flat_number && ` · кв. ${request.flat_number}`}
          </Typography.Text>
        </Flex>
      </Flex>

      <Flex align="center" gap={8}>
        <Typography.Text
          className={cn(styles.Pill, styles[tone])}
          variant="label-strong"
        >
          {STATUS_LABEL[request.status]}
        </Typography.Text>
        {request.group_size > 1 && (
          <Typography.Text
            className={cn(styles.Pill, styles.neutral)}
            variant="label-strong"
          >
            {request.group_size}{" "}
            {plural(request.group_size, ["квартира", "квартиры", "квартир"])} в
            заявке
          </Typography.Text>
        )}
      </Flex>

      {isRunning && <DeadlinePanel request={request} />}

      <div className={styles.Responsible}>
        <Flex align="center" gap={12}>
          <Icon src={buildingIcon} className={styles.RowIcon} />
          <Flex align="stretch" direction="column" gapY={2}>
            <Typography.Text variant="description" color="secondary">
              Отвечает
            </Typography.Text>
            <Typography.Text variant="body-strong" color="primary">
              {zone && zone !== "management"
                ? ZONE_LABEL[zone]
                : (request.org_name ?? "Управляющая компания дома")}
            </Typography.Text>
          </Flex>
        </Flex>

        {zone && zone !== "management" && (
          <Typography.Text variant="description" color="secondary">
            {request.org_name ?? "Управляющая компания"} приняла заявку и
            передала её ответственной организации.
          </Typography.Text>
        )}

        {request.executor_name && (
          <Flex align="center" gap={12}>
            <Icon src={userIcon} className={styles.RowIcon} />
            <Flex align="stretch" direction="column" gapY={2}>
              <Typography.Text variant="description" color="secondary">
                Исполнитель
              </Typography.Text>
              <Typography.Text variant="body-strong" color="primary">
                {request.executor_name}
              </Typography.Text>
            </Flex>
          </Flex>
        )}
      </div>

      <Flex asChild align="stretch" direction="column" gap={8}>
        <section>
          <Typography.Text asChild variant="title" color="primary">
            <h2>Ход заявки</h2>
          </Typography.Text>
          <RequestTimeline steps={timeline} />
        </section>
      </Flex>

      {request.messages.length > 0 && (
        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>Ответы УК</h2>
            </Typography.Text>
            <Answers messages={request.messages} />
          </section>
        </Flex>
      )}
    </div>
  );
};

export const Component = RequestPage;
