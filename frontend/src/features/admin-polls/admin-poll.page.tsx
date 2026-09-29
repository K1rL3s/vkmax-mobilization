import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { generatePath, Link } from "react-router-dom";

import {
  authorCaption,
  deadlineLabel,
  PollOption,
  QuorumPanel,
} from "@/features/meetings";
import { Routes } from "@/shared/model/routes";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import { ErrorState, LoadingState } from "@/shared/ui/state";
import { StatusPill } from "@/shared/ui/status-pill";

import { useAdminPoll } from "./use-admin-poll";

import styles from "./admin-poll.module.css";

const AdminPollPage = () => {
  const { poll, results, address, noticeId, closing, ...view } = useAdminPoll();

  if (view.isPending) {
    return <LoadingState fill title="Загружаем опрос" />;
  }

  if (view.isError || !poll || !results) {
    return <ErrorState error={view.loadError} fill onRetry={view.retry} />;
  }

  const isActive = poll.status === "active";

  return (
    <Panel className={styles.Page} mode="secondary">
      <div className={styles.Content}>
        <Flex align="stretch" direction="column" gapY={4}>
          <Flex align="flex-start" gap={8}>
            <Typography.Text
              asChild
              className={styles.Grow}
              variant="header"
              color="primary"
            >
              <h1 className={styles.Title}>{poll.title}</h1>
            </Typography.Text>

            <StatusPill tone={isActive ? "themed" : "neutral"}>
              {isActive ? "Идёт" : "Завершён"}
            </StatusPill>
          </Flex>

          {address && (
            <Typography.Text variant="body" color="secondary">
              {address}
            </Typography.Text>
          )}

          <Typography.Text variant="description" color="secondary">
            {authorCaption(poll.created_by_role)} · {deadlineLabel(poll)}
            {poll.is_multiple && " · можно выбрать несколько вариантов"}
          </Typography.Text>
        </Flex>

        {poll.description && (
          <Typography.Text variant="body" color="primary">
            {poll.description}
          </Typography.Text>
        )}

        <Typography.Text variant="description" color="secondary">
          Это {poll.disclaimer}
        </Typography.Text>

        <Flex align="stretch" direction="column" gap={8}>
          {poll.options.map((option) => (
            <PollOption
              key={option.id}
              option={option}
              result={results.options.find(
                (item) => item.option_id === option.id,
              )}
              isMine={false}
              isSelected={false}
              isMultiple={poll.is_multiple}
              selectable={false}
              onToggle={() => {}}
            />
          ))}
        </Flex>

        <QuorumPanel results={results} />

        {noticeId !== undefined && (
          <Button asChild size="medium" variant="secondary">
            <Link
              to={generatePath(Routes.ADMIN_ANNOUNCEMENT_REGISTER, {
                announcementId: String(noticeId),
              })}
            >
              Реестр уведомлений
            </Link>
          </Button>
        )}
      </div>

      {isActive && (
        <div className={styles.Footer}>
          <Button
            size="large"
            stretched
            variant="secondary"
            disabled={!poll.can_manage}
            onClick={closing.ask}
          >
            Завершить опрос
          </Button>

          <Typography.Text variant="description" color="secondary">
            {poll.can_manage
              ? "Голосование завершится сразу, результаты останутся"
              : "Завершить опрос может его организатор или сотрудник УК, которая управляет домом"}
          </Typography.Text>
        </div>
      )}

      <ConfirmDialog
        isOpen={closing.isOpen}
        title="Завершить опрос?"
        description="Голосование закроется сразу и обратно не откроется. Результаты и голоса останутся на месте."
        confirmLabel="Завершить"
        error={closing.error}
        isPending={closing.isPending}
        onConfirm={closing.confirm}
        onClose={closing.dismiss}
      />
    </Panel>
  );
};

export const Component = AdminPollPage;
