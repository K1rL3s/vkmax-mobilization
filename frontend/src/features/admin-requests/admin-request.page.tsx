import type { ReactNode } from "react";
import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { generatePath, Link } from "react-router-dom";

import {
  buildTimeline,
  CATEGORY_ICON,
  DeadlinePanel,
  isFinished,
  isOnReview,
  RequestTimeline,
  STATUS_LABEL,
  STATUS_TONE,
} from "@/features/request";
import { isForbidden } from "@/shared/api/errors";
import { formatDayTime, plural } from "@/shared/lib/format";
import { Routes } from "@/shared/model/routes";
import { Card } from "@/shared/ui/card";
import { IconTile } from "@/shared/ui/icon-tile";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";
import { StatusPill } from "@/shared/ui/status-pill";

import { CHANNEL_LABEL } from "./domain/request-workflow";
import { useAdminRequest } from "./model/use-admin-request";
import { NoOrgAccess } from "./ui/no-org-access";
import { RequestAssignment } from "./ui/request-assignment";
import { RequestConversation } from "./ui/request-conversation";
import { RequestPhotos } from "./ui/request-photos";
import { RequestStatusAction } from "./ui/request-status-action";

import styles from "./admin-requests.module.css";

const AdminRequestPage = () => {
  const { valid, query } = useAdminRequest();
  if (!valid)
    return (
      <EmptyState
        fill
        title="Неверный адрес заявки"
        description="Откройте заявку из списка."
        action={
          <Button asChild>
            <Link to={Routes.ADMIN_REQUESTS}>К заявкам</Link>
          </Button>
        }
      />
    );
  if (isForbidden(query.error)) return <NoOrgAccess />;
  if (query.isPending) return <LoadingState fill title="Загружаем заявку…" />;
  if (query.isError)
    return <ErrorState fill onRetry={() => void query.refetch()} />;
  const request = query.data;

  const tone = STATUS_TONE[request.status];
  const isRunning = !isFinished(request.status) && !isOnReview(request.status);
  const isAssignable =
    request.status === "accepted" ||
    request.status === "in_progress" ||
    request.status === "on_review";

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
          <Typography.Text asChild variant="title" color="primary">
            <h1>Заявка №{request.id}</h1>
          </Typography.Text>
          <Typography.Text variant="description" color="secondary">
            {request.address}
          </Typography.Text>
        </Flex>
      </Flex>

      <Flex align="center" wrap="wrap" gap={8}>
        <StatusPill tone={tone}>{STATUS_LABEL[request.status]}</StatusPill>
        <StatusPill tone="neutral">{request.category_label}</StatusPill>
        {request.group_id != null && (
          <Typography.Text asChild variant="description-strong">
            <Link
              className={styles.Link}
              to={generatePath(Routes.ADMIN_REQUEST_GROUP, {
                groupId: String(request.group_id),
              })}
            >
              Коллективная · {request.group_size}{" "}
              {plural(request.group_size, ["квартира", "квартиры", "квартир"])}
            </Link>
          </Typography.Text>
        )}
        {request.parent_request_id != null && (
          <Typography.Text asChild variant="description-strong">
            <Link
              className={styles.Link}
              to={generatePath(Routes.ADMIN_REQUEST, {
                requestId: String(request.parent_request_id),
              })}
            >
              Повторно по заявке №{request.parent_request_id}
            </Link>
          </Typography.Text>
        )}
      </Flex>

      {isRunning && <DeadlinePanel request={request} />}

      <Card>
        <dl className={styles.Facts}>
          <Fact label={request.author_name ? "Житель" : "Звонил в УК"}>
            {request.author_name ?? request.caller_name ?? "не записан"}
          </Fact>
          {request.caller_phone && (
            <Fact label="Телефон">
              <a className={styles.Link} href={`tel:${request.caller_phone}`}>
                {request.caller_phone}
              </a>
            </Fact>
          )}
          <Fact label="Квартира">{request.flat_number ?? "не указана"}</Fact>
          <Fact label="Подана">{formatDayTime(request.created_at)}</Fact>
          {request.channel !== "miniapp" && (
            <Fact label="Как поступила">{CHANNEL_LABEL[request.channel]}</Fact>
          )}
          {request.executor_name && (
            <Fact label="Исполнитель">{request.executor_name}</Fact>
          )}
        </dl>
      </Card>

      <Flex asChild align="stretch" direction="column" gap={8}>
        <section>
          <Typography.Text asChild variant="title" color="primary">
            <h2>Что случилось</h2>
          </Typography.Text>
          <Card>
            <Typography.Text
              className={styles.Text}
              variant="body"
              color="primary"
            >
              {request.description}
            </Typography.Text>
          </Card>
        </section>
      </Flex>

      <RequestPhotos title="Фото проблемы" files={request.photos} />

      {isAssignable && <RequestAssignment request={request} />}

      <RequestPhotos title="Фото результата" files={request.result_photos} />

      <Flex asChild align="stretch" direction="column" gap={8}>
        <section>
          <Typography.Text asChild variant="title" color="primary">
            <h2>Ход заявки</h2>
          </Typography.Text>
          <RequestTimeline steps={buildTimeline(request, "staff")} />
        </section>
      </Flex>

      <RequestStatusAction target={{ kind: "request", request }} />

      <RequestConversation request={request} />
    </Panel>
  );
};

const Fact = ({ label, children }: { label: string; children: ReactNode }) => (
  <div>
    <Typography.Text asChild variant="description" color="secondary">
      <dt>{label}</dt>
    </Typography.Text>
    <Typography.Text asChild variant="description-strong">
      <dd>{children}</dd>
    </Typography.Text>
  </div>
);

export const Component = AdminRequestPage;
