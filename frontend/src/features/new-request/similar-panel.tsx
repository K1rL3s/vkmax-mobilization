import { Button, Flex, Typography } from "@maxhub/max-ui";

import { plural } from "@/shared/lib/format";
import { userIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import styles from "./similar-panel.module.css";

type SimilarPanelProps = {
  count: number;
  canJoin: boolean;
  isJoining: boolean;
  onJoin: () => void;
};

export const SimilarPanel = ({
  count,
  canJoin,
  isJoining,
  onJoin,
}: SimilarPanelProps) => (
  <div className={styles.Panel}>
    <Flex align="center" gap={12}>
      <IconTile icon={userIcon} tone="themed" />
      <Typography.Text variant="body-strong" color="primary">
        {count} {plural(count, ["сосед", "соседа", "соседей"])} уже{" "}
        {plural(count, ["сообщил", "сообщили", "сообщили"])} о той же проблеме
      </Typography.Text>
    </Flex>

    {canJoin && (
      <Button
        size="medium"
        variant="secondary"
        stretched
        loading={isJoining}
        onClick={onJoin}
      >
        Присоединиться к заявке
      </Button>
    )}
  </div>
);
