import { Button, CellSimple, Flex, Panel, Typography } from "@maxhub/max-ui";
import { generatePath, Link } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import { ErrorState, LoadingState } from "@/shared/ui/state";

import { authorCaption, deadlineLabel, voteNote } from "./domain/poll";
import { useClosePoll } from "./model/use-close-poll";
import { usePoll } from "./model/use-poll";
import { PollOption } from "./ui/poll-option";
import { QuorumPanel } from "./ui/quorum-panel";

import styles from "./poll.module.css";

const PollPage = () => {
  const view = usePoll();
  const { poll, results, residency } = view;
  const closing = useClosePoll(poll?.id ?? 0);

  if (view.isPending) {
    return <LoadingState fill title="Загружаем опрос" />;
  }

  if (view.isError || !poll || !results) {
    return <ErrorState error={view.loadError} fill onRetry={view.retry} />;
  }

  const isVoting = poll.can_vote && !poll.voted;
  const note = voteNote(poll, residency);

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex align="stretch" direction="column" gapY={4}>
        <Typography.Text asChild variant="title" color="primary">
          <h1>{poll.title}</h1>
        </Typography.Text>

        <Typography.Text variant="description" color="secondary">
          {authorCaption(poll.created_by_role)} · {deadlineLabel(poll)}
        </Typography.Text>
      </Flex>

      {poll.description && (
        <Typography.Text variant="body" color="primary">
          {poll.description}
        </Typography.Text>
      )}

      <Typography.Text className={styles.Disclaimer} variant="description">
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
            isMine={poll.my_option_ids.includes(option.id)}
            isSelected={view.chosen.includes(option.id)}
            isMultiple={poll.is_multiple}
            selectable={isVoting}
            onToggle={() => view.toggle(option.id)}
          />
        ))}
      </Flex>

      {isVoting && (
        <Flex align="stretch" direction="column" gapY={8}>
          <Button
            size="large"
            stretched
            disabled={!view.canSend}
            loading={view.isVoting}
            onClick={view.send}
          >
            Проголосовать
          </Button>

          <Typography.Text variant="description" color="secondary">
            {poll.is_multiple
              ? "Можно выбрать несколько вариантов. Изменить голос после отправки нельзя."
              : "Изменить голос после отправки нельзя."}
          </Typography.Text>

          {view.isVoteFailed && (
            <Typography.Text className={styles.Failed} variant="description">
              Голос не отправился. Проверьте связь и попробуйте ещё раз.
            </Typography.Text>
          )}
        </Flex>
      )}

      {note && (
        <Flex align="stretch" direction="column" gapY={8}>
          <Typography.Text variant="description" color="secondary">
            {note.text}
          </Typography.Text>

          {note.confirm && residency && (
            <Button asChild size="medium" variant="secondary">
              <Link
                to={generatePath(Routes.FLAT_CONFIRMATION, {
                  residentId: String(residency.resident_id),
                })}
                state={{
                  returnTo: generatePath(Routes.MEETING, {
                    pollId: String(poll.id),
                  }),
                }}
              >
                Подтвердить квартиру
              </Link>
            </Button>
          )}
        </Flex>
      )}

      <QuorumPanel results={results} />

      {poll.can_manage && (
        <div className={styles.Panel}>
          <CellSimple
            asChild
            title="Непроголосовавшие квартиры"
            subtitle="Видно организатору опроса"
            showChevron
          >
            <Link
              to={generatePath(Routes.MEETING_NON_VOTERS, {
                pollId: String(poll.id),
              })}
            />
          </CellSimple>
        </div>
      )}

      {poll.can_manage && poll.status === "active" && (
        <Button size="medium" variant="secondary" onClick={closing.ask}>
          Завершить опрос
        </Button>
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

export const Component = PollPage;
