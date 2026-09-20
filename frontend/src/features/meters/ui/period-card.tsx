import { Flex, Typography } from "@maxhub/max-ui";

import { Icon, clockIcon } from "@/shared/ui/icon";

import { formatPeriod, type ReadingPeriod } from "../domain/reading";

import styles from "./period-card.module.css";

type PeriodCardProps = {
  period: ReadingPeriod;
  flatNumber: string | null;
};

export const PeriodCard = ({ period, flatNumber }: PeriodCardProps) => {
  const flat = flatNumber === null ? null : `кв. ${flatNumber}`;
  const state = period.is_submitted
    ? "Показания уже отправлены, можно переподать"
    : "Окно подачи открыто";

  return (
    <Flex align="center" gap={12} className={styles.Card}>
      <Icon src={clockIcon} className={styles.Icon} />
      <Flex direction="column" align="stretch" gapY={2} className={styles.Text}>
        <Typography.Text variant="detail-strong" color="primary">
          Показания за {formatPeriod(period.period)}
        </Typography.Text>
        <Typography.Text variant="description" color="secondary">
          {[state, flat].filter(Boolean).join(" · ")}
        </Typography.Text>
      </Flex>
    </Flex>
  );
};
