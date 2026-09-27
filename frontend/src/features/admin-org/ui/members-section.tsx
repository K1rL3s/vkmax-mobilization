import { CellSimple, Flex, IconButton, Typography } from "@maxhub/max-ui";
import { useNavigate } from "react-router-dom";

import { errorMessage } from "@/shared/api/errors";
import { formatDay } from "@/shared/lib/format";
import { orgParams, useSession } from "@/shared/model/session";
import { Routes } from "@/shared/model/routes";
import { ConfirmDialog, useConfirm } from "@/shared/ui/confirm-dialog";
import { Icon, trashIcon, usersIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";
import { StatusPill, type StatusPillTone } from "@/shared/ui/status-pill";

import {
  removeBlock,
  ROLE_LABEL,
  ROLE_ORDER,
  type OrgMember,
  type OrgRole,
} from "../domain/roles";
import { useOrgMembers, useRemoveMember } from "../model/use-org";

import styles from "./members-section.module.css";

const ROLE_TONE: Record<OrgRole, StatusPillTone> = {
  creator: "promo",
  admin: "themed",
  employee: "neutral",
  executor: "positive",
};

const byRole = (a: OrgMember, b: OrgMember) =>
  ROLE_ORDER.indexOf(a.role) - ROLE_ORDER.indexOf(b.role) ||
  a.created_at.localeCompare(b.created_at);

const MemberRow = ({
  member,
  isMe,
  separator,
  onRemove,
}: {
  member: OrgMember;
  isMe: boolean;
  separator: boolean;
  onRemove: () => void;
}) => {
  const blocked = removeBlock(member);
  const caption = [
    isMe && "Вы",
    member.username && `@${member.username}`,
    `в команде с ${formatDay(member.created_at)}`,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <CellSimple
      separator={separator}
      innerClassNames={{ title: styles.Title, content: styles.Content }}
      title={
        <Flex align="center" gap={8} wrap="wrap">
          <span className={styles.Name}>{member.name}</span>
          <StatusPill tone={ROLE_TONE[member.role]}>
            {ROLE_LABEL[member.role]}
          </StatusPill>
        </Flex>
      }
      subtitle={caption}
      after={
        !blocked && (
          <IconButton
            size="small"
            variant="secondary"
            disabled={blocked !== null}
            aria-label={blocked ?? `Исключить: ${member.name}`}
            onClick={onRemove}
          >
            <Icon src={trashIcon} size={20} />
          </IconButton>
        )
      }
    />
  );
};

export const MembersSection = () => {
  const navigate = useNavigate();
  const { session } = useSession();
  const members = useOrgMembers();
  const remove = useRemoveMember();
  const confirm = useConfirm<OrgMember>();

  const content = () => {
    if (members.isPending)
      return <LoadingState title="Загружаем сотрудников" />;

    if (members.isError)
      return (
        <ErrorState
          error={members.error}
          description="Не получилось загрузить сотрудников"
          onRetry={() => void members.refetch()}
        />
      );

    if (members.data.length === 0)
      return (
        <EmptyState
          icon={usersIcon}
          title="В команде пока никого"
          description="Пригласите сотрудников и исполнителей ссылкой: они появятся здесь, когда откроют её в MAX"
        />
      );

    return (
      <div className={styles.Panel}>
        {[...members.data].sort(byRole).map((member, index) => (
          <MemberRow
            key={member.user_id}
            member={member}
            isMe={member.user_id === session?.user_id}
            separator={index > 0}
            onRemove={() => {
              remove.reset();
              confirm.ask(member);
            }}
          />
        ))}
      </div>
    );
  };

  return (
    <Flex asChild align="stretch" direction="column" gapY={8}>
      <section className={styles.MembersSection}>
        <Typography.Text asChild variant="title" color="primary">
          <h2>Команда</h2>
        </Typography.Text>

        {content()}

        <div className={styles.Panel}>
          <CellSimple
            before={<Icon src={usersIcon} className={styles.CellIcon} />}
            title="Приглашения"
            subtitle="Ссылки для новых сотрудников и исполнителей"
            showChevron
            onClick={() => void navigate(Routes.ADMIN_ORG_INVITES)}
          />
        </div>

        <ConfirmDialog
          isOpen={confirm.isOpen}
          title={`Исключить: ${confirm.target?.name ?? ""}?`}
          description={
            confirm.target &&
            (confirm.target.role === "executor"
              ? "Бот перестанет присылать ему заявки. Уже назначенные заявки передайте другому исполнителю"
              : "Доступ к кабинету УК закроется сразу. Вернуть человека можно новым приглашением")
          }
          confirmLabel="Исключить"
          error={
            remove.isError &&
            errorMessage(
              remove.error,
              "Не получилось исключить. Проверьте связь и попробуйте ещё раз",
            )
          }
          isPending={remove.isPending}
          onConfirm={() => {
            if (confirm.target)
              remove.mutate(
                {
                  params: {
                    ...orgParams(),
                    path: { user_id: confirm.target.user_id },
                  },
                },
                { onSuccess: confirm.dismiss },
              );
          }}
          onClose={confirm.dismiss}
        />
      </section>
    </Flex>
  );
};
