import { useState } from "react";
import { Button, Flex, Grid, IconButton, Typography } from "@maxhub/max-ui";
import { useCopy } from "@siberiacancode/reactuse";

import { cn } from "@/shared/lib/css";
import { formatDayTime } from "@/shared/lib/format";
import { getWebApp } from "@/shared/lib/max";
import { Icon, trashIcon } from "@/shared/ui/icon";
import { StatusPill, type StatusPillTone } from "@/shared/ui/status-pill";

import {
  canRevoke,
  type InviteState,
  type OrgInvite,
} from "../domain/invite-state";
import { ROLE_LABEL } from "../domain/roles";

import styles from "./invite-card.module.css";

const STATE: Record<InviteState, { label: string; tone: StatusPillTone }> = {
  live: { label: "Действует", tone: "positive" },
  exhausted: { label: "Все активации использованы", tone: "neutral" },
  expired: { label: "Истекло", tone: "neutral" },
  revoked: { label: "Отозвано", tone: "negative" },
};

type InviteCardProps = {
  invite: OrgInvite;
  state: InviteState;
  onRevoke?: () => void;
  className?: string;
};

const Fact = ({ label, value }: { label: string; value: string }) => (
  <Flex direction="column" gapY={2}>
    <Typography.Text variant="description" color="secondary">
      {label}
    </Typography.Text>
    <Typography.Text variant="body" color="primary">
      {value}
    </Typography.Text>
  </Flex>
);

export const InviteCard = ({
  invite,
  state,
  onRevoke,
  className,
}: InviteCardProps) => {
  const link = useCopy(2000);
  const [copyFailed, setCopyFailed] = useState(false);
  const status = STATE[state];
  const isLive = state === "live";
  const webApp = getWebApp();

  const copy = () => {
    setCopyFailed(false);
    link.copy(invite.deeplink).catch(() => setCopyFailed(true));
  };

  // отказ от шеринга - тоже отказ промиса, сообщать о нём нечего
  const share = () =>
    void webApp
      ?.shareMaxContent({
        text: `Приглашение в команду управляющей компании, роль: ${ROLE_LABEL[invite.role].toLowerCase()}`,
        link: invite.deeplink,
      })
      .catch(() => undefined);

  return (
    <Flex
      className={cn(styles.InviteCard, className)}
      align="stretch"
      direction="column"
      gapY={12}
    >
      <Flex align="center" gap={8}>
        <Flex className={styles.Grow} align="center" gap={8} wrap="wrap">
          <StatusPill tone="themed">{ROLE_LABEL[invite.role]}</StatusPill>
          <StatusPill tone={status.tone}>{status.label}</StatusPill>
        </Flex>

        {onRevoke && canRevoke(state) && (
          <IconButton
            size="small"
            variant="secondary"
            aria-label="Отозвать приглашение"
            onClick={onRevoke}
          >
            <Icon src={trashIcon} size={20} />
          </IconButton>
        )}
      </Flex>

      <Typography.Text
        className={cn(styles.Link, !isLive && styles.dead)}
        variant="description"
        color={isLive ? "primary" : "tertiary"}
      >
        {invite.deeplink}
      </Typography.Text>

      <Grid cols={2} gap={12}>
        <Fact label="Создано" value={formatDayTime(invite.created_at)} />
        {invite.revoked_at ? (
          <Fact label="Отозвано" value={formatDayTime(invite.revoked_at)} />
        ) : (
          <Fact
            label={state === "expired" ? "Истекло" : "Действует до"}
            value={formatDayTime(invite.expires_at)}
          />
        )}
        <Fact
          label="Активации"
          value={`${invite.activations_used} из ${invite.max_activations}`}
        />
      </Grid>

      {isLive && (
        <Flex align="center" gap={8} wrap="wrap">
          <Button size="small" variant="secondary" onClick={copy}>
            {link.copied ? "Скопировано" : "Скопировать"}
          </Button>

          <Button
            size="small"
            variant="secondary"
            disabled={!webApp}
            onClick={share}
          >
            Поделиться
          </Button>
        </Flex>
      )}

      {copyFailed && (
        <Typography.Text className={styles.Error} variant="description">
          Не получилось скопировать. Выделите ссылку выше и скопируйте вручную
        </Typography.Text>
      )}
    </Flex>
  );
};
