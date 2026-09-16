import { Button, Container, Flex, Panel, Typography } from "@maxhub/max-ui";

import styles from "./onboarding.module.css";

const OnboardingPage = () => {
  return (
    <Panel className={styles.Page} centeredX centeredY>
      <Container>
        <Flex direction="column" align="center" gap={36}>
          <div className={styles.Icon}>Z</div>
          <Flex
            className={styles.Hero}
            direction="column"
            align="center"
            gapY={6}
          >
            <Typography.Headline variant="large-strong">
              Жека Коммуналкин
            </Typography.Headline>

            <Typography.Body variant="large" className={styles.Subtitle}>
              Всё для вашего дома в одном чате: заявки в УК, показания
              счётчиков, опросы жильцов
            </Typography.Body>
          </Flex>

          <Button>Добавить недвижимость</Button>
        </Flex>
      </Container>
    </Panel>
  );
};

export const Component = OnboardingPage;
