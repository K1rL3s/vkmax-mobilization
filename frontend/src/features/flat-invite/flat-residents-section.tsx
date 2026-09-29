import { Fragment, useState } from "react";
import { Button, CellSimple, Flex, Typography } from "@maxhub/max-ui";

import { errorMessage } from "@/shared/api/errors";
import { authParams } from "@/shared/api/instance";
import { useSession, type Residency } from "@/shared/model/session";
import { ConfirmDialog, useConfirm } from "@/shared/ui/confirm-dialog";
import { Icon, userIcon, usersIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { InviteCard } from "./invite-card";
import { IssueInviteDialog } from "./issue-invite-dialog";
import {
  useEndTenancy,
  useFlatInvites,
  useFlatResidents,
  useFlatTenancies,
  useRevokeInvite,
  type FlatInvite,
  type FlatResident,
} from "./use-flat-invites";

import styles from "./flat-residents-section.module.css";

const residentCaption = (resident: FlatResident) =>
  [
    resident.role === "owner" ? "Собственник" : "Арендатор · по приглашению",
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
    ? `Вы вошли по приглашению собственника, поэтому ${closed.join(" и ")}`
    : null;
};

const Note = ({ children }: { children: string }) => (
  <Typography.Text variant="description" color="secondary">
    {children}
  </Typography.Text>
);

const Residents = ({
  flatId,
  userId,
  canEnd,
}: {
  flatId: number;
  userId: number;
  canEnd: boolean;
}) => {
  const residents = useFlatResidents(flatId);
  const end = useEndTenancy();
  const confirm = useConfirm<FlatResident>();

  if (residents.isPending) {
    return <LoadingState title="Загружаем жителей" />;
  }

  if (residents.isError) {
    return (
      <ErrorState
        error={residents.error}
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
        description="Здесь появятся собственники и арендаторы, вошедшие по приглашению"
      />
    );
  }

  const list = [...residents.data].sort(
    (a, b) => Number(b.user_id === userId) - Number(a.user_id === userId),
  );

  return (
    <>
      <div className={styles.Panel}>
        {list.map((resident, index) => (
          <Fragment key={resident.resident_id}>
            <CellSimple
              separator={index > 0}
              before={<Icon src={userIcon} />}
              title={resident.user_id === userId ? "Вы" : resident.name}
              subtitle={residentCaption(resident)}
            />
            {canEnd && resident.role === "tenant" && (
              <div className={styles.End}>
                <Button
                  size="small"
                  variant="secondary"
                  onClick={() => {
                    end.reset();
                    confirm.ask(resident);
                  }}
                >
                  Завершить аренду
                </Button>
              </div>
            )}
          </Fragment>
        ))}
      </div>

      <ConfirmDialog
        isOpen={confirm.isOpen}
        title="Завершить аренду?"
        description="Арендатор потеряет доступ к квартире: показания, заявки от квартиры. Уже поданные заявки останутся"
        confirmLabel="Завершить аренду"
        error={
          end.isError &&
          errorMessage(
            end.error,
            "Не получилось завершить аренду. Попробуйте ещё раз",
          )
        }
        isPending={end.isPending}
        onConfirm={() => {
          if (confirm.target) {
            end.mutate(
              {
                params: {
                  ...authParams(),
                  path: {
                    flat_id: flatId,
                    resident_id: confirm.target.resident_id,
                  },
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

const day = (iso: string) => new Date(iso).toLocaleDateString("ru-RU");

const PastTenants = ({ flatId }: { flatId: number }) => {
  const tenancies = useFlatTenancies(flatId);

  if (!tenancies.data?.length) {
    return null;
  }

  return (
    <>
      <Typography.Text variant="body-strong" color="primary">
        Арендаторы раньше
      </Typography.Text>

      <div className={styles.Panel}>
        {tenancies.data.map((tenancy, index) => (
          <CellSimple
            key={tenancy.id}
            separator={index > 0}
            before={<Icon src={userIcon} />}
            title={tenancy.name}
            subtitle={`с ${day(tenancy.started_at)} по ${day(tenancy.ended_at)}`}
          />
        ))}
      </div>
    </>
  );
};

const Invites = ({ flatId }: { flatId: number }) => {
  const [isIssuing, setIssuing] = useState(false);
  const invites = useFlatInvites(flatId);
  const revoke = useRevokeInvite(flatId);
  const confirm = useConfirm<FlatInvite>();

  const content = () => {
    if (invites.isPending) {
      return <LoadingState title="Загружаем приглашения" />;
    }

    if (invites.isError) {
      return (
        <ErrorState
          error={invites.error}
          description="Не получилось загрузить приглашения"
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
        Пригласить в квартиру
      </Button>

      <Note>
        {invites.data?.length === 0
          ? "Приглашение впускает арендатора в квартиру. Арендатор не видит начисления и не голосует в опросах"
          : "Арендатор не видит начисления и не голосует в опросах"}
      </Note>

      <IssueInviteDialog
        flatId={flatId}
        isOpen={isIssuing}
        onClose={() => setIssuing(false)}
      />

      <ConfirmDialog
        isOpen={confirm.isOpen}
        title="Отозвать приглашение?"
        description="По нему больше никто не войдёт. Тех, кто уже вошёл, это не выселит: завершите им аренду в списке жителей"
        confirmLabel="Отозвать"
        error={
          revoke.isError &&
          "Не получилось отозвать приглашение. Попробуйте ещё раз"
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
            "Приглашение в квартиру выдаёт собственник квартиры"}
        </Note>
      );
    }

    if (!residency.verified) {
      return (
        <Note>
          Жителей квартиры и приглашения для арендатора видно после
          подтверждения квартиры
        </Note>
      );
    }

    return <Invites flatId={flatId} />;
  };

  return (
    <Flex asChild align="stretch" direction="column" gap={8}>
      <section className={styles.FlatResidentsSection}>
        <Typography.Text asChild variant="title" color="primary">
          <h2>Жители квартиры</h2>
        </Typography.Text>

        {residency.verified && (
          <Residents
            flatId={flatId}
            userId={session.user_id}
            canEnd={residency.role === "owner"}
          />
        )}

        {residency.verified && residency.role === "owner" && (
          <PastTenants flatId={flatId} />
        )}

        {invites()}
      </section>
    </Flex>
  );
};
