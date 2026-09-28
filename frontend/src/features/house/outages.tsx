import { Flex, Typography } from "@maxhub/max-ui";

import { formatDayTime } from "@/shared/lib/format";
import { alertIcon, Icon } from "@/shared/ui/icon";
import { StatusPill } from "@/shared/ui/status-pill";

import { outageTitle, type Outage } from "./outage";

import styles from "./outages.module.css";

type OutagesPanelProps = { outages: Outage[] };

export const OutagesPanel = ({ outages }: OutagesPanelProps) => {
  if (outages.length === 0) {
    return null;
  }

  return (
    <Flex asChild align="stretch" direction="column" gap={8}>
      <section>
        <Typography.Text asChild variant="title" color="primary">
          <h2>Отключения</h2>
        </Typography.Text>
        {outages.map((outage) => (
          <div
            key={`${outage.resource}-${outage.starts_at}`}
            className={styles.Outage}
          >
            <Flex align="center" gap={8}>
              <Icon src={alertIcon} size={20} className={styles.Icon} />
              <Typography.Text variant="body-strong" color="primary">
                {outageTitle(outage)}
              </Typography.Text>
            </Flex>
            <Typography.Text variant="description" color="secondary">
              С {formatDayTime(outage.starts_at)} · {outage.reason} ·{" "}
              {outage.company}
            </Typography.Text>
            <Typography.Text variant="description" color="tertiary">
              {outage.recalc_hint}
            </Typography.Text>
            {outage.is_demo && (
              <StatusPill tone="themed">демо-данные</StatusPill>
            )}
          </div>
        ))}
      </section>
    </Flex>
  );
};
