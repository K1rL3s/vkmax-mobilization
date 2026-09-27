import { Flex, Panel, Typography } from "@maxhub/max-ui";

import { alertIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import styles from "./outside-max.module.css";

const OutsideMaxPage = () => {
  return (
    <Panel className={styles.Page} centeredX centeredY>
      <Flex
        className={styles.Content}
        direction="column"
        align="center"
        gap={36}
      >
        <IconTile icon={alertIcon} tone="negative" size="xlarge" />

        <Flex
          className={styles.Hero}
          direction="column"
          align="center"
          gapY={6}
        >
          <Typography.Text asChild variant="header" color="primary">
            <h1>Откройте Жэку в MAX</h1>
          </Typography.Text>

          <Typography.Text variant="body" color="secondary">
            Жэка работает только внутри мессенджера MAX: оттуда приложение
            узнаёт, кто вы и какой у вас дом. Найдите бота «Жэка Коммуналкин» в
            MAX и нажмите «Открыть».
          </Typography.Text>
        </Flex>
      </Flex>
    </Panel>
  );
};

export const Component = OutsideMaxPage;
