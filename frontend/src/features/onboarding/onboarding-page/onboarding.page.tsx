import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { buildingIcon } from "@/shared/assets/icons";
import { Routes } from "@/shared/model/routes";
import { IconTile } from "@/shared/ui/icon-tile";

import styles from "./onboarding.module.css";

const OnboardingPage = () => {
  return (
    <Panel className={styles.Page} centeredX centeredY>
      <Flex
        className={styles.Content}
        direction="column"
        align="center"
        gap={36}
      >
        <IconTile icon={buildingIcon} tone="secondary" size="xlarge" />

        <Flex
          className={styles.Hero}
          direction="column"
          align="center"
          gapY={6}
        >
          <Typography.Text asChild variant="header" color="primary">
            <h1>Жека Коммуналкин</h1>
          </Typography.Text>

          <Typography.Text variant="body" color="secondary">
            Всё для вашего дома в одном чате: заявки в УК, показания счётчиков,
            опросы жильцов
          </Typography.Text>
        </Flex>

        <Button asChild size="large" stretched>
          <Link to={Routes.ONBOARDING_HOUSE}>Добавить недвижимость</Link>
        </Button>
      </Flex>
    </Panel>
  );
};

export const Component = OnboardingPage;
