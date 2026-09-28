import { Flex, Panel, Typography } from "@maxhub/max-ui";
import { generatePath, Link } from "react-router-dom";

import { formatDay, formatTime, plural } from "@/shared/lib/format";
import { Routes } from "@/shared/model/routes";
import { buildingIcon, Icon, userIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { ErrorState, LoadingState } from "@/shared/ui/state";
import { StatusPill } from "@/shared/ui/status-pill";

import { CATEGORY_ICON, ZONE_LABEL } from "./domain/category";
import { deadlineLeft } from "./domain/format";
import {
  currentActor,
  isFinished,
  isOnReview,
  STATUS_LABEL,
  STATUS_TONE,
} from "./domain/status";
import { buildTimeline } from "./domain/timeline";
import { useRequest } from "./model/use-request";
import { ReviewPanel } from "./review";
import { Answers } from "./ui/answers";
import { DeadlinePanel } from "./ui/deadline-panel";
import { EscalationPanel } from "./ui/escalation-panel";
import { RatePanel } from "./ui/rate-panel";
import { RequestPhotos } from "./ui/request-photos";
import { RequestTimeline } from "./ui/request-timeline";

import styles from "./request.module.css";

const RequestPage = () => {
  const { request, zone, isPending, isError, loadError, retry } = useRequest();

  if (isPending) {
    return <LoadingState fill title="Загружаем заявку" />;
  }

  if (isError || !request) {
    return <ErrorState fill error={loadError} onRetry={retry} />;
  }

  const tone = STATUS_TONE[request.status];
  const isRunning = !isFinished(request.status) && !isOnReview(request.status);
  const overdue = isRunning && deadlineLeft(request.deadline_at)?.overdue;
  const actor = currentActor(request);

  return (
    <Panel className={styles.Page} mode="secondary">
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
          {request.parent_request_id && (
            <Typography.Text
              asChild
              className={styles.Parent}
              variant="description"
            >
              <Link
                to={generatePath(Routes.REQUEST, {
                  requestId: String(request.parent_request_id),
                })}
              >
                Повторно по заявке №{request.parent_request_id}
              </Link>
            </Typography.Text>
          )}
        </Flex>
      </Flex>

      <Flex align="center" gap={8}>
        <StatusPill tone={tone}>{STATUS_LABEL[request.status]}</StatusPill>
        {request.group_size > 1 && (
          <StatusPill tone="neutral">
            {request.group_size}{" "}
            {plural(request.group_size, ["квартира", "квартиры", "квартир"])} в
            заявке
          </StatusPill>
        )}
      </Flex>

      {actor && (
        <Typography.Text variant="description" color="secondary">
          Сейчас: {actor}
        </Typography.Text>
      )}

      {isRunning && <DeadlinePanel request={request} />}

      {request.can_review && <ReviewPanel request={request} />}

      {(request.can_rate || request.rating !== null) && (
        <RatePanel request={request} />
      )}

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

      {overdue && <EscalationPanel request={request} />}

      <Flex asChild align="stretch" direction="column" gap={8}>
        <section>
          <Typography.Text asChild variant="title" color="primary">
            <h2>Ход заявки</h2>
          </Typography.Text>
          <RequestTimeline steps={buildTimeline(request)} />
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

      {!request.can_review && (
        <RequestPhotos title="Ваши фото" files={request.photos} />
      )}
    </Panel>
  );
};

export const Component = RequestPage;
