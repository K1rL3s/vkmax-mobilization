import { useEffect } from "react";
import { Flex, Grid, Panel, Typography } from "@maxhub/max-ui";
import { useLocation } from "react-router-dom";

import { isForbidden } from "@/shared/api/errors";
import { formatDay, plural } from "@/shared/lib/format";
import { useSession } from "@/shared/model/session";
import { Icon, infoIcon } from "@/shared/ui/icon";
import { ErrorState, LoadingState } from "@/shared/ui/state";
import { StatusPill } from "@/shared/ui/status-pill";

import { ROLE_LABEL } from "./domain/roles";
import { useActorRole, useOrgCard, useOrgSettings } from "./model/use-org";
import { MembersSection } from "./ui/members-section";
import { OrgSwitcher } from "./ui/org-switcher";
import { SettingsForm } from "./ui/settings-form";

import styles from "./admin-org.module.css";

const Field = ({ label, value }: { label: string; value: string }) => (
  <Flex align="stretch" direction="column" gapY={2}>
    <Typography.Text variant="detail" color="secondary">
      {label}
    </Typography.Text>
    <Typography.Text variant="body" color="primary">
      {value}
    </Typography.Text>
  </Flex>
);

const AdminOrgPage = () => {
  const { hash } = useLocation();
  const { currentOrg } = useSession();
  const role = useActorRole();
  const card = useOrgCard();
  const settings = useOrgSettings();

  const readOnly = isForbidden(card.error);
  const isReady = settings.isSuccess && (card.isSuccess || readOnly);

  useEffect(() => {
    if (isReady && hash)
      document.getElementById(hash.slice(1))?.scrollIntoView();
  }, [isReady, hash]);

  if (settings.isPending || card.isPending)
    return <LoadingState fill title="Загружаем организацию" />;

  if (!isReady)
    return (
      <ErrorState
        fill
        onRetry={() => {
          void card.refetch();
          void settings.refetch();
        }}
      />
    );

  const org = card.data;
  const isDemo = org?.is_demo ?? currentOrg?.is_demo;

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex align="stretch" direction="column" gapY={4}>
        <Flex align="center" gap={8}>
          <Typography.Text
            asChild
            className={styles.Grow}
            variant="title"
            color="primary"
          >
            <h1>{org?.name ?? currentOrg?.name ?? "Организация"}</h1>
          </Typography.Text>

          {isDemo && <StatusPill tone="themed">демо</StatusPill>}
        </Flex>

        {role && (
          <Typography.Text variant="description" color="secondary">
            Ваша роль: {ROLE_LABEL[role].toLowerCase()}
          </Typography.Text>
        )}
      </Flex>

      <OrgSwitcher />

      {org ? (
        <div className={styles.Card}>
          <Grid cols={2} gap={12}>
            <Field label="ИНН" value={org.inn} />
            <Field label="Лицензия" value={org.license_no ?? "не указана"} />
          </Grid>

          <Field label="Адрес" value={org.address} />

          <Typography.Text variant="description" color="secondary">
            {[
              `${org.houses_count} ${plural(org.houses_count, ["дом", "дома", "домов"])}`,
              `${org.members_count} ${plural(org.members_count, ["человек", "человека", "человек"])} в команде`,
              org.registered_at &&
                `в сервисе с ${formatDay(org.registered_at)}`,
            ]
              .filter(Boolean)
              .join(" · ")}
          </Typography.Text>
        </div>
      ) : (
        <Flex align="center" gap={12} className={styles.Note}>
          <Icon src={infoIcon} size={20} className={styles.NoteIcon} />
          <Typography.Text variant="description" color="secondary">
            Карточку организации, команду и приглашения видят создатель и
            администраторы. Настройки ниже открыты только для чтения
          </Typography.Text>
        </Flex>
      )}

      <SettingsForm settings={settings.data} readOnly={readOnly} />

      {!readOnly && <MembersSection />}
    </Panel>
  );
};

export const Component = AdminOrgPage;
