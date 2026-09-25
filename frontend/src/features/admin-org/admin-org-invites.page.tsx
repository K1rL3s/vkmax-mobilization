import { useState } from "react";
import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";

import { errorDetail, isForbidden } from "@/shared/api/errors";
import { orgParams } from "@/shared/model/session";
import { ConfirmDialog, useConfirm } from "@/shared/ui/confirm-dialog";
import { usersIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import {
  inviteState,
  type InviteState,
  type OrgInvite,
} from "./domain/invite-state";
import { useActorRole, useOrgInvites, useRevokeInvite } from "./model/use-org";
import { InviteCard } from "./ui/invite-card";
import { InviteDialog } from "./ui/invite-dialog";

import styles from "./admin-org-invites.module.css";

const Group = ({
  title,
  invites,
  onRevoke,
}: {
  title: string;
  invites: { invite: OrgInvite; state: InviteState }[];
  onRevoke: (invite: OrgInvite) => void;
}) => {
  if (invites.length === 0) return null;

  return (
    <Flex asChild align="stretch" direction="column" gapY={8}>
      <section>
        <Typography.Text asChild variant="title" color="primary">
          <h2>{title}</h2>
        </Typography.Text>

        {invites.map(({ invite, state }) => (
          <InviteCard
            key={invite.code}
            invite={invite}
            state={state}
            onRevoke={() => onRevoke(invite)}
          />
        ))}
      </section>
    </Flex>
  );
};

const AdminOrgInvitesPage = () => {
  const [isCreating, setCreating] = useState(false);
  const [now] = useState(() => Date.now());
  const actor = useActorRole();
  const invites = useOrgInvites();
  const revoke = useRevokeInvite();
  const confirm = useConfirm<OrgInvite>();

  if (invites.isPending)
    return <LoadingState fill title="Загружаем приглашения" />;

  if (isForbidden(invites.error))
    return (
      <EmptyState
        fill
        icon={usersIcon}
        title="Приглашения недоступны"
        description="Приглашать в команду и видеть ссылки могут создатель и администраторы организации"
      />
    );

  if (invites.isError)
    return <ErrorState fill onRetry={() => void invites.refetch()} />;

  const items = invites.data.map((invite) => ({
    invite,
    state: inviteState(invite, now),
  }));
  const live = items.filter((item) => item.state === "live");
  const rest = items.filter((item) => item.state !== "live");

  const askRevoke = (invite: OrgInvite) => {
    revoke.reset();
    confirm.ask(invite);
  };

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex align="stretch" direction="column" gapY={4}>
        <Typography.Text asChild variant="title" color="primary">
          <h1>Приглашения</h1>
        </Typography.Text>

        <Typography.Text variant="description" color="secondary">
          Ссылка открывает бота и добавляет человека в команду с выбранной ролью
        </Typography.Text>
      </Flex>

      <Button size="large" stretched onClick={() => setCreating(true)}>
        Пригласить в команду
      </Button>

      {invites.data.length === 0 ? (
        <EmptyState
          icon={usersIcon}
          title="Приглашений пока нет"
          description="Создайте ссылку и отправьте её сотруднику или исполнителю в MAX. Здесь будет видно, сколько человек по ней вошло"
        />
      ) : (
        <>
          <Group title="Действуют" invites={live} onRevoke={askRevoke} />
          <Group
            title="Больше не действуют"
            invites={rest}
            onRevoke={askRevoke}
          />
        </>
      )}

      <InviteDialog
        actor={actor}
        isOpen={isCreating}
        onClose={() => setCreating(false)}
      />

      <ConfirmDialog
        isOpen={confirm.isOpen}
        title="Отозвать приглашение?"
        description="Ссылка перестанет работать. Те, кто уже вошёл по ней, останутся в команде, исключить их можно в списке команды"
        confirmLabel="Отозвать"
        error={
          revoke.isError &&
          (errorDetail(revoke.error) ??
            "Не получилось отозвать. Проверьте связь и попробуйте ещё раз")
        }
        isPending={revoke.isPending}
        onConfirm={() => {
          if (confirm.target)
            revoke.mutate(
              {
                params: { ...orgParams(), path: { code: confirm.target.code } },
              },
              { onSuccess: confirm.dismiss },
            );
        }}
        onClose={confirm.dismiss}
      />
    </Panel>
  );
};

export const Component = AdminOrgInvitesPage;
