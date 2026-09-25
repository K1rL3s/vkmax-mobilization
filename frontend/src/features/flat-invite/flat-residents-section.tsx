import { useState } from "react";
import { Button, CellSimple, Flex, Typography } from "@maxhub/max-ui";

import { authParams } from "@/shared/api/instance";
import { useSession, type Residency } from "@/shared/model/session";
import { ConfirmDialog, useConfirm } from "@/shared/ui/confirm-dialog";
import { Icon, userIcon, usersIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { InviteCard } from "./invite-card";
import { IssueInviteDialog } from "./issue-invite-dialog";
import {
  useFlatInvites,
  useFlatResidents,
  useRevokeInvite,
  type FlatInvite,
  type FlatResident,
} from "./use-flat-invites";

import styles from "./flat-residents-section.module.css";

const residentCaption = (resident: FlatResident) =>
  [
    resident.role === "owner" ? "Собственник" : "Арендатор · вход по коду",
    resident.is_chairman && "председатель совета",
    !resident.verified && "не подтверждён",
    resident.status === "blocked" && "доступ закрыт УК",
  ]
    .filter(Boolean)
    .join(" · ");

const restrictions = (residency: Residency) => {
  const closed = [
    !residency.can_see_charges && "не видите начисления",
    !residency.can_vote && "не голосуете в опросах",
  ].filter(Boolean);

  return closed.length > 0
    ? `Вы вошли по коду собственника, поэтому ${closed.join(" и ")}`
    : null;
};

const Note = ({ children }: { children: string }) => (
  <Typography.Text variant="description" color="secondary">
    {children}
  </Typography.Text>
);

const Residents = ({ flatId, userId }: { flatId: number; userId: number }) => {
  const residents = useFlatResidents(flatId);

  if (residents.isPending) {
    return <LoadingState title="Загружаем жителей" />;
  }

  if (residents.isError) {
    return (
      <ErrorState
        description="Не получилось загрузить жителей"
        onRetry={() => void residents.refetch()}
      />
    );
  }

  if (residents.data.length === 0) {
    return (
      <EmptyState
        icon={usersIcon}
        title="Жителей пока нет"
        description="Здесь появятся собственники и арендаторы, вошедшие по коду"
      />
    );
  }

  const list = [...residents.data].sort(
    (a, b) => Number(b.user_id === userId) - Number(a.user_id === userId),
  );

  return (
    <div className={styles.Panel}>
      {list.map((resident, index) => (
        <CellSimple
          key={resident.resident_id}
          separator={index > 0}
          before={<Icon src={userIcon} />}
          title={resident.user_id === userId ? "Вы" : resident.name}
          subtitle={residentCaption(resident)}
        />
      ))}
    </div>
  );
};

const Invites = ({ flatId }: { flatId: number }) => {
  const [isIssuing, setIssuing] = useState(false);
  const invites = useFlatInvites(flatId);
  const revoke = useRevokeInvite(flatId);
  const confirm = useConfirm<FlatInvite>();

  const content = () => {
    if (invites.isPending) {
      return <LoadingState title="Загружаем коды" />;
    }

    if (invites.isError) {
      return (
        <ErrorState
          description="Не получилось загрузить выданные коды"
          onRetry={() => void invites.refetch()}
        />
      );
    }

    return invites.data.map((invite) => (
      <InviteCard
        key={invite.code}
        invite={invite}
        onRevoke={() => {
          revoke.reset();
          confirm.ask(invite);
        }}
      />
    ));
  };

  return (
    <>
      {content()}

      <Button
        size="large"
        stretched
        variant="secondary"
        onClick={() => setIssuing(true)}
      >
        Выдать код
      </Button>

      <Note>
        {invites.data?.length === 0
          ? "Код впускает арендатора в квартиру. Арендатор не видит начисления и не голосует в опросах"
          : "Арендатор не видит начисления и не голосует в опросах"}
      </Note>

      <IssueInviteDialog
        flatId={flatId}
        isOpen={isIssuing}
        onClose={() => setIssuing(false)}
      />

      <ConfirmDialog
        isOpen={confirm.isOpen}
        title={`Отозвать код ${confirm.target?.code ?? ""}?`}
        description="По нему больше никто не войдёт. Тех, кто уже вошёл, это не выселит"
        confirmLabel="Отозвать"
        error={
          revoke.isError && "Не получилось отозвать код. Попробуйте ещё раз"
        }
        isPending={revoke.isPending}
        onConfirm={() => {
          if (confirm.target) {
            revoke.mutate(
              {
                params: {
                  ...authParams(),
                  path: { code: confirm.target.code },
                },
              },
              { onSuccess: confirm.dismiss },
            );
          }
        }}
        onClose={confirm.dismiss}
      />
    </>
  );
};

export const FlatResidentsSection = () => {
  const { session, currentResidency: residency } = useSession();
  const flatId = residency?.flat_id;

  if (!session || !residency || flatId == null) {
    return null;
  }

  const invites = () => {
    if (residency.role === "tenant") {
      return (
        <Note>
          {restrictions(residency) ??
            "Код для арендатора выдаёт собственник квартиры"}
        </Note>
      );
    }

    if (!residency.verified) {
      return (
        <Note>Выдать код арендатору можно после подтверждения квартиры</Note>
      );
    }

    return <Invites flatId={flatId} />;
  };

  return (
    <Flex asChild align="stretch" direction="column" gap={12}>
      <section className={styles.FlatResidentsSection}>
        <Typography.Text asChild variant="title" color="primary">
          <h2>Жители квартиры</h2>
        </Typography.Text>

        <Residents flatId={flatId} userId={session.user_id} />

        {invites()}
      </section>
    </Flex>
  );
};
