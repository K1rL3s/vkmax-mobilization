import { Button, Flex, Typography } from "@maxhub/max-ui";

import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";

import { cn } from "@/shared/lib/css";
import { formatDayTime } from "@/shared/lib/format";

import { NO_NORM } from "../domain/category";
import { deadlineLeft, deadlineProgress } from "../domain/format";
import type { RequestCard } from "../domain/types";
import { refetchRequests } from "../model/use-repeat-request";

import styles from "./deadline-panel.module.css";

type DeadlineSource = Pick<
  RequestCard,
  | "id"
  | "can_demo_expire"
  | "created_at"
  | "status"
  | "deadline_at"
  | "react_deadline_at"
  | "deadline_text"
  | "deadline_basis"
>;

export const DeadlinePanel = ({ request }: { request: DeadlineSource }) => {
  const left = deadlineLeft(request.deadline_at);
  const progress = deadlineProgress(request.created_at, request.deadline_at);

  return (
    <div className={styles.Panel}>
      <Flex align="center" gap={8}>
        <Typography.Text
          className={styles.Grow}
          variant="body-strong"
          color="primary"
        >
          Срок
        </Typography.Text>
        {left && (
          <Typography.Text
            className={cn(styles.Left, left.overdue && styles.overdue)}
            variant="description"
          >
            {left.text}
          </Typography.Text>
        )}
      </Flex>

      {progress !== null && (
        <div className={styles.Track}>
          <div
            className={cn(styles.Fill, left?.overdue && styles.overdue)}
            style={{ width: `${progress * 100}%` }}
          />
        </div>
      )}

      {request.status === "new" && request.react_deadline_at && (
        <Typography.Text variant="description" color="secondary">
          Принять до {formatDayTime(request.react_deadline_at)}
        </Typography.Text>
      )}
      <Typography.Text variant="description" color="secondary">
        {request.deadline_at &&
          `${left?.overdue ? "Срок истёк" : "Выполнить до"} ${formatDayTime(request.deadline_at)} · `}
        срок {request.deadline_text}
      </Typography.Text>
      <Typography.Text variant="description" color="secondary">
        {request.deadline_basis ?? NO_NORM}
      </Typography.Text>
      {request.can_demo_expire && <DemoExpireButton requestId={request.id} />}
    </div>
  );
};

const DemoExpireButton = ({ requestId }: { requestId: number }) => {
  const expire = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/demo/expire",
    { onSuccess: refetchRequests },
  );

  return (
    <>
      <Button
        size="medium"
        variant="secondary"
        stretched
        loading={expire.isPending}
        onClick={() =>
          expire.mutate({
            params: { ...authParams(), path: { request_id: requestId } },
          })
        }
      >
        ⏩ Демо: срок истек
      </Button>
      {expire.error && (
        <Typography.Text variant="description" className={styles.Failed}>
          {errorMessage(
            expire.error,
            "Срок не сдвинулся. Проверьте связь и попробуйте ещё раз",
          )}
        </Typography.Text>
      )}
    </>
  );
};
