import { Button, Flex, Typography } from "@maxhub/max-ui";

import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { Card } from "@/shared/ui/card";
import { FieldError } from "@/shared/ui/field-error";
import { alertIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import styles from "./demand-card.module.css";

type DemandCardProps = {
  houseId: number;
  demandSent: boolean;
  demandCount: number;
  orgEmail: string | null;
  onSent: () => void;
};

export const DemandCard = ({
  houseId,
  demandSent,
  demandCount,
  orgEmail,
  onSent,
}: DemandCardProps) => {
  const demand = rqClient.useMutation("post", "/api/houses/{house_id}/demand", {
    onSuccess: onSent,
  });

  return (
    <Flex asChild align="stretch" direction="column" gap={12}>
      <Card>
        <Flex align="center" gap={12}>
          <IconTile icon={alertIcon} tone="neutral" />
          <Flex
            className={styles.Grow}
            align="stretch"
            direction="column"
            gapY={2}
          >
            <Typography.Text variant="body-strong" color="primary">
              УК пока не подключена к сервису
            </Typography.Text>
            <Typography.Text variant="description" color="secondary">
              Заявки и показания счётчиков станут доступны, когда управляющая
              компания подключится. Пока можно связаться с ней напрямую
            </Typography.Text>
          </Flex>
        </Flex>

        {demandSent ? (
          <Typography.Text variant="description" color="secondary">
            Мы передадим спрос управляющей компании. Сервиса здесь ждут:{" "}
            {demandCount}
          </Typography.Text>
        ) : (
          <Button
            size="medium"
            stretched
            loading={demand.isPending}
            onClick={() =>
              demand.mutate({
                params: { ...authParams(), path: { house_id: houseId } },
              })
            }
          >
            Мне нужен
          </Button>
        )}

        {orgEmail && (
          <>
            <Typography.Text variant="description" color="secondary">
              Напишите УК, что ждёте её в Жэке
            </Typography.Text>
            <Button asChild size="medium" variant="secondary" stretched>
              <a href={`mailto:${orgEmail}`}>Написать в УК</a>
            </Button>
          </>
        )}

        {demand.isError && (
          <FieldError
            message={errorMessage(
              demand.error,
              "Не получилось отправить. Попробуйте ещё раз",
            )}
          />
        )}
      </Card>
    </Flex>
  );
};
