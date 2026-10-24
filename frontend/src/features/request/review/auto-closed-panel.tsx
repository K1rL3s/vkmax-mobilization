import { Button, Typography } from "@maxhub/max-ui";

import { formatShortDay } from "@/shared/lib/format";
import type { RequestCard } from "../domain/types";

import { RejectionFields } from "./rejection-fields";
import { useRejection } from "./use-rejection";

import styles from "./auto-closed-panel.module.css";

export const AutoClosedPanel = ({
  request,
  returnUntil,
}: {
  request: RequestCard;
  returnUntil: string;
}) => {
  const rejection = useRejection(request, "«Проблема осталась»");

  return (
    <div className={styles.Panel}>
      <Typography.Text variant="body-strong" color="primary">
        Заявка закрылась сама
      </Typography.Text>
      <Typography.Text variant="description" color="secondary">
        {`Работу не проверили за 48 часов. Если проблема осталась, сообщите до ${formatShortDay(returnUntil)} - создадим повторную заявку со ссылкой на эту`}
      </Typography.Text>

      <RejectionFields rejection={rejection} />

      {rejection.error && (
        <Typography.Text variant="description" className={styles.Failed}>
          {rejection.error}
        </Typography.Text>
      )}

      <Button
        size="medium"
        stretched
        loading={rejection.isSending}
        disabled={!rejection.canSend}
        onClick={rejection.send}
      >
        Проблема осталась
      </Button>

      {rejection.missing && (
        <Typography.Text variant="detail" color="secondary">
          {rejection.missing}
        </Typography.Text>
      )}
    </div>
  );
};
