import { Button, Flex, Typography } from "@maxhub/max-ui";

import { authParams, rqClient } from "@/shared/api/instance";
import { Card } from "@/shared/ui/card";
import { alertIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import styles from "./home.module.css";

type DemandCardProps = {
  houseId: number;
  demandSent: boolean;
  demandCount: number;
  onSent: () => void;
};

export const DemandCard = ({
  houseId,
  demandSent,
  demandCount,
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

        {demand.isError && (
          <Typography.Text variant="description" color="secondary">
            Не получилось отправить. Попробуйте ещё раз
          </Typography.Text>
        )}
      </Card>
    </Flex>
  );
};
