import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { errorMessage } from "@/shared/api/errors";
import { Routes } from "@/shared/model/routes";
import { Checkbox } from "@/shared/ui/checkbox";
import { ErrorState } from "@/shared/ui/state";
import { StatusPill } from "@/shared/ui/status-pill";

import { useConsent } from "./model/use-consent";

import zheka from "./zheka.webp";
import styles from "./onboarding.module.css";

export const Consent = ({
  notice,
  onContinue,
}: {
  notice?: string;
  onContinue: () => Promise<void>;
}) => {
  const consent = useConsent(onContinue);

  return (
    <Panel className={styles.Page} centeredX centeredY>
      <Flex
        className={styles.Content}
        direction="column"
        align="center"
        gap={32}
      >
        <Flex direction="column" align="center" gap={16}>
          {notice && <StatusPill tone="positive">{notice}</StatusPill>}

          <img src={zheka} alt="" className={styles.Mascot} />

          <Flex
            className={styles.Hero}
            direction="column"
            align="center"
            gapY={4}
          >
            <Typography.Text asChild variant="header" color="primary">
              <h1>Жэка Коммуналкин</h1>
            </Typography.Text>

            <Typography.Text variant="body" color="secondary">
              Заявки в УК, показания счётчиков и опросы жильцов вашего дома
            </Typography.Text>
          </Flex>
        </Flex>

        <Flex
          className={styles.Footer}
          align="stretch"
          direction="column"
          gap={16}
        >
          <Checkbox
            className={styles.Consent}
            checked={consent.checked}
            onChange={consent.setChecked}
          >
            <Typography.Text variant="description" color="primary">
              Соглашаюсь на обработку персональных данных
            </Typography.Text>

            <Typography.Text asChild variant="description">
              <Link className={styles.Policy} to={Routes.PRIVACY}>
                Политика обработки данных
              </Link>
            </Typography.Text>
          </Checkbox>

          {consent.error && (
            <ErrorState
              title="Не получилось сохранить согласие"
              description={errorMessage(
                consent.error,
                "Проверьте связь и попробуйте ещё раз",
              )}
              error={consent.error}
              onRetry={consent.start}
            />
          )}

          <Button
            size="large"
            stretched
            loading={consent.isPending}
            disabled={!consent.checked}
            onClick={consent.start}
          >
            {consent.label}
          </Button>
        </Flex>
      </Flex>
    </Panel>
  );
};
