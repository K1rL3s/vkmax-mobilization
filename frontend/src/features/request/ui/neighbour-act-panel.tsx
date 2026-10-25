import { Button, Flex, Typography } from "@maxhub/max-ui";

import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";

import type { RequestCard } from "../domain/types";

import styles from "./neighbour-act-panel.module.css";

export const NeighbourActPanel = ({ request }: { request: RequestCard }) => {
  const pdf = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/neighbour-act-pdf",
  );

  return (
    <div className={styles.Panel}>
      <Flex align="stretch" direction="column" gapY={2}>
        <Typography.Text variant="body-strong" color="primary">
          Акт с соседями
        </Typography.Text>
        <Typography.Text variant="description" color="secondary">
          Если УК не проверила услугу, акт можно составить без неё: подписывают
          двое соседей и председатель совета дома (ПП № 354, п. 110(1)). По акту
          просят перерасчёт. Бот пришлёт PDF с данными заявки, впишите замеры и
          соберите подписи
        </Typography.Text>
      </Flex>

      <Button
        size="medium"
        stretched
        loading={pdf.isPending}
        disabled={pdf.isSuccess}
        onClick={() =>
          pdf.mutate({
            params: { ...authParams(), path: { request_id: request.id } },
          })
        }
      >
        {pdf.isSuccess ? "Отправили в чат с ботом" : "Акт с соседями (PDF)"}
      </Button>
      {pdf.error && (
        <Typography.Text variant="description" className={styles.Failed}>
          {errorMessage(
            pdf.error,
            "Не получилось отправить. Проверьте связь и попробуйте ещё раз",
          )}
        </Typography.Text>
      )}
    </div>
  );
};
