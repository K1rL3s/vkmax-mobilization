import { Button, Flex, Typography } from "@maxhub/max-ui";

import { duration, formatDayTime } from "@/shared/lib/format";
import { autoClose } from "../domain/timeline";
import type { RequestCard } from "../domain/types";

import { AttachmentPair } from "./attachment-pair";
import { RejectionFields } from "./rejection-fields";
import { useReview } from "./use-review";

import styles from "./review-panel.module.css";

export const ReviewPanel = ({ request }: { request: RequestCard }) => {
  const form = useReview(request);
  const closing = autoClose(request);

  return (
    <div className={styles.Panel}>
      <Flex align="center" gap={8}>
        <Typography.Text
          className={styles.Grow}
          variant="body-strong"
          color="primary"
        >
          Проверьте работу
        </Typography.Text>
        {closing !== null && closing.left > 0 && (
          <Typography.Text className={styles.Left} variant="description">
            осталось {duration(closing.left)}
          </Typography.Text>
        )}
      </Flex>

      {closing !== null && (
        <>
          <div className={styles.Track}>
            <div
              className={styles.Fill}
              style={{ width: `${closing.progress * 100}%` }}
            />
          </div>
          <Typography.Text variant="description" color="secondary">
            Без ответа заявка закроется как выполненная{" "}
            {formatDayTime(closing.at)}
          </Typography.Text>
        </>
      )}

      <AttachmentPair request={request} doneAt={closing?.sentAt ?? null} />

      <RejectionFields rejection={form.rejection} />

      {form.error && (
        <Typography.Text variant="description" className={styles.Failed}>
          {form.error}
        </Typography.Text>
      )}

      <Flex direction="row-reverse" wrap="wrap" gap={8}>
        <Button
          className={styles.Action}
          size="medium"
          loading={form.isAccepting}
          disabled={!form.canAccept}
          onClick={form.accept}
        >
          Принять
        </Button>
        <Button
          className={styles.Action}
          size="medium"
          variant="secondary"
          loading={form.rejection.isSending}
          disabled={!form.canReject}
          onClick={form.rejection.send}
        >
          Сделано плохо
        </Button>
      </Flex>

      <Typography.Text variant="detail" color="secondary">
        {form.rejection.missing ??
          "«Сделано плохо» создаст повторную заявку со ссылкой на эту"}
      </Typography.Text>

      {form.canDemoAutoClose && (
        <Flex align="flex-start" direction="column" gapY={4}>
          <Button
            size="small"
            variant="secondary"
            loading={form.isAutoClosing}
            onClick={form.demoAutoClose}
          >
            Демо: закрыть без проверки
          </Button>
          {form.autoCloseError && (
            <Typography.Text variant="description" className={styles.Failed}>
              {form.autoCloseError}
            </Typography.Text>
          )}
        </Flex>
      )}
    </div>
  );
};
