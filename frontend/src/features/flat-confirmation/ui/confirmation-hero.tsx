import { Flex, Typography } from "@maxhub/max-ui";

import { IconTile, type IconTileTone } from "@/shared/ui/icon-tile";

import styles from "./confirmation-hero.module.css";

type ConfirmationHeroProps = {
  icon: string;
  tone: IconTileTone;
  title: string;
  address: string;
};

export const ConfirmationHero = ({
  icon,
  tone,
  title,
  address,
}: ConfirmationHeroProps) => {
  return (
    <Flex className={styles.Hero} direction="column" align="center" gapY={12}>
      <IconTile icon={icon} tone={tone} size="xlarge" />

      <Flex direction="column" align="center" gapY={6}>
        <Typography.Text asChild variant="header" color="primary">
          <h1>{title}</h1>
        </Typography.Text>

        <Typography.Text variant="body" color="secondary">
          {address}
        </Typography.Text>
      </Flex>
    </Flex>
  );
};
