import { Flex, Grid, IconButton, Typography } from "@maxhub/max-ui";
import { useCopy } from "@siberiacancode/reactuse";

import { cn } from "@/shared/lib/css";
import { duration, formatDayTime, plural } from "@/shared/lib/format";
import { checkIcon, copyIcon, Icon, trashIcon } from "@/shared/ui/icon";

import type { FlatInvite } from "./use-flat-invites";

import styles from "./invite-card.module.css";

type InviteCardProps = {
  invite: FlatInvite;
  onRevoke?: () => void;
  className?: string;
};

const HOUR = 60 * 60 * 1000;

const timeLeft = (expiresAt: string) =>
  duration(Math.round((Date.parse(expiresAt) - Date.now()) / HOUR) * HOUR);

const Fact = ({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) => (
  <Flex direction="column" gapY={2}>
    <Typography.Text variant="description" color="secondary">
      {label}
    </Typography.Text>
    <Typography.Text variant="body-strong" color="primary">
      {value}
    </Typography.Text>
    <Typography.Text variant="description" color="secondary">
      {hint}
    </Typography.Text>
  </Flex>
);

export const InviteCard = ({
  invite,
  onRevoke,
  className,
}: InviteCardProps) => {
  const link = useCopy(2000);
  const left = invite.max_activations - invite.activations_used;

  return (
    <Flex
      className={cn(styles.InviteCard, className)}
      align="stretch"
      direction="column"
      gapY={12}
    >
      <Flex align="flex-start" gap={8}>
        <Flex className={styles.Grow} direction="column" gapY={2}>
          <Typography.Text variant="description" color="secondary">
            Код для арендатора
          </Typography.Text>
          <span className={styles.Code}>{invite.code}</span>
        </Flex>

        <IconButton
          size="small"
          variant="secondary"
          aria-label={link.copied ? "Ссылка скопирована" : "Скопировать ссылку"}
          onClick={() => void link.copy(invite.deeplink)}
        >
          <Icon src={link.copied ? checkIcon : copyIcon} size={20} />
        </IconButton>

        {onRevoke && (
          <IconButton
            size="small"
            variant="secondary"
            aria-label="Отозвать код"
            onClick={onRevoke}
          >
            <Icon src={trashIcon} size={20} />
          </IconButton>
        )}
      </Flex>

      <Grid cols={2} gap={12}>
        <Fact
          label="Действует до"
          value={formatDayTime(invite.expires_at)}
          hint={`ещё ${timeLeft(invite.expires_at)}`}
        />
        <Fact
          label="Активации"
          value={`${invite.activations_used} из ${invite.max_activations}`}
          hint={`${plural(left, ["осталась", "осталось", "осталось"])} ${left}`}
        />
      </Grid>

      {link.copied && (
        <Typography.Text variant="description" color="secondary">
          Ссылка с кодом скопирована, отправьте её арендатору
        </Typography.Text>
      )}
    </Flex>
  );
};
