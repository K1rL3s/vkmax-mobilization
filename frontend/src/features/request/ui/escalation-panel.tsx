import { Button, Flex, Typography } from "@maxhub/max-ui";
import { useCopy } from "@siberiacancode/reactuse";

import { useHouseCard } from "@/features/house";
import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { formatShortDay, formatTime } from "@/shared/lib/format";

import { gjiAppeal } from "../domain/gji";
import type { RequestCard } from "../domain/types";
import { refetchRequests } from "../model/use-repeat-request";

import styles from "./escalation-panel.module.css";

export const EscalationPanel = ({ request }: { request: RequestCard }) => {
  const house = useHouseCard(request.house_id);
  const copy = useCopy(2000);
  const escalate = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/escalate",
    { onSuccess: refetchRequests },
  );

  const text = house.data ? gjiAppeal(request, house.data) : null;

  return (
    <div className={styles.Panel}>
      <Flex align="stretch" direction="column" gapY={2}>
        <Typography.Text variant="title" color="primary">
          1. Попросить руководство УК
        </Typography.Text>
        <Typography.Text variant="description" color="secondary">
          {request.escalated_at
            ? `Руководство УК уведомлено ${formatShortDay(request.escalated_at)} в ${formatTime(request.escalated_at)}`
            : "Руководство УК получит сообщение, а заявка встанет первой в списке УК"}
        </Typography.Text>
      </Flex>

      {!request.escalated_at && (
        <Button
          size="large"
          stretched
          loading={escalate.isPending}
          onClick={() =>
            escalate.mutate({
              params: { ...authParams(), path: { request_id: request.id } },
            })
          }
        >
          Попросить руководство УК
        </Button>
      )}
      {escalate.error && (
        <Typography.Text variant="description" className={styles.Failed}>
          {errorMessage(
            escalate.error,
            "Не получилось отправить. Проверьте связь и попробуйте ещё раз",
          )}
        </Typography.Text>
      )}

      {text && (
        <>
          <Flex align="stretch" direction="column" gapY={2}>
            <Typography.Text variant="title" color="primary">
              2. Жалоба в ГЖИ
            </Typography.Text>
            <Typography.Text variant="description" color="secondary">
              Мы подготовили текст с данными заявки. Скопируйте и отправьте в
              жилищную инспекцию, если посчитаете нужным
            </Typography.Text>
          </Flex>

          <Typography.Text asChild variant="description" color="primary">
            <pre className={styles.Appeal}>{text}</pre>
          </Typography.Text>

          <Button
            size="large"
            variant="secondary"
            stretched
            onClick={() => void copy.copy(text)}
          >
            {copy.copied ? "Текст скопирован" : "Скопировать текст"}
          </Button>
        </>
      )}
    </div>
  );
};
