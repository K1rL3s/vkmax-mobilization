import { Button, Flex, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import type { HouseCard } from "@/features/house";
import { Routes } from "@/shared/model/routes";
import { Card } from "@/shared/ui/card";
import { alertIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import { emergencyContact } from "./emergency-contact";

import styles from "./emergency-card.module.css";

export const EmergencyCard = ({ org }: { org: HouseCard["org"] }) => {
  const contact = emergencyContact(org);

  return (
    <Flex asChild align="stretch" direction="column" gap={12}>
      <Card>
        <Flex align="center" gap={12}>
          <IconTile icon={alertIcon} tone="negative" />
          <Flex
            className={styles.Grow}
            align="stretch"
            direction="column"
            gapY={2}
          >
            <Typography.Text variant="body-strong" className={styles.Title}>
              Авария
            </Typography.Text>
            <Typography.Text variant="description" color="secondary">
              Пожар, газ, потоп или искрит проводка - сначала позвоните
            </Typography.Text>
          </Flex>
        </Flex>

        <Flex gap={8} wrap="wrap">
          <Button
            asChild
            size="medium"
            variant="destructive"
            className={styles.Call}
          >
            <a href="tel:112" aria-label="Позвонить 112">
              112
            </a>
          </Button>
          <Button
            asChild
            size="medium"
            variant="secondary"
            className={styles.Call}
          >
            <a href="tel:104" aria-label="Позвонить в газовую службу 104">
              104
            </a>
          </Button>
          {contact && (
            <Button
              asChild
              size="medium"
              variant="secondary"
              className={styles.Call}
            >
              <a href={`tel:${contact.phone}`} aria-label={contact.label}>
                {contact.short}
              </a>
            </Button>
          )}
        </Flex>

        <Button asChild size="medium" variant="secondary" stretched>
          <Link to={Routes.EMERGENCY}>Что делать при аварии?</Link>
        </Button>
      </Card>
    </Flex>
  );
};
