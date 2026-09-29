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
        <Typography.Text
          className={styles.Grow}
          variant="body-strong"
          color="primary"
        >
          Сравнить себя с другими УК
        </Typography.Text>

        <Chevron />
      </Tappable>
    </Flex>
  );
};
