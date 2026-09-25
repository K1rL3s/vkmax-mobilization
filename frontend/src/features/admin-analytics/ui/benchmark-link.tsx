import { Flex, Tappable, Typography } from "@maxhub/max-ui";
import { useNavigate } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { Chevron } from "@/shared/ui/chevron";

import styles from "./benchmark-link.module.css";

export const BenchmarkLink = () => {
  const navigate = useNavigate();

  return (
    <Flex asChild align="center" gap={12}>
      <Tappable
        className={styles.Link}
        onClick={() => void navigate(Routes.ADMIN_BENCHMARK)}
      >
        <Flex
          className={styles.Grow}
          direction="column"
          align="stretch"
          gapY={2}
        >
          <Typography.Text variant="body-strong" color="primary">
            Сравнение с платформой
          </Typography.Text>

          <Typography.Text variant="detail" color="secondary">
            Ваши показатели против медианы, названий других УК не показываем
          </Typography.Text>
        </Flex>

        <Chevron />
      </Tappable>
    </Flex>
  );
};
