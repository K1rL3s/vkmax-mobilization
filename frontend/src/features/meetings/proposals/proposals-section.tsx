import { Button, Textarea, Typography } from "@maxhub/max-ui";
import { generatePath, useNavigate } from "react-router-dom";

import { errorMessage } from "@/shared/api/errors";
import { Routes } from "@/shared/model/routes";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import { FieldError } from "@/shared/ui/field-error";

import { proposalFormConstraints } from "./proposal";
import { ProposalRow } from "./proposal-row";
import { useAnswerProposal, useProposals } from "./use-proposals";

import styles from "./proposals.module.css";

export const ProposalsSection = () => {
  const navigate = useNavigate();
  const view = useProposals();
  const answering = useAnswerProposal();

  if (!view.isVisible) {
    return null;
  }

  return (
    <section className={styles.Section}>
      <Typography.Text asChild variant="title" color="primary">
        <h2>Предложения совету дома</h2>
      </Typography.Text>

      {!view.isChairman && !view.hasChairman && !view.isPending && (
        <Typography.Text variant="description" color="secondary">
          В доме пока нет председателя совета. Как только его выберут,
          предложение можно будет отправить.
        </Typography.Text>
      )}

      {!view.isChairman && view.hasChairman && (
        <>
          <Typography.Text variant="description" color="secondary">
            Председатель прочитает предложение и ответит. Вашего имени он не
            увидит.
          </Typography.Text>

          <Textarea
            rows={3}
            mode="secondary"
            placeholder="Например: поставить лавочку у третьего подъезда"
            maxLength={proposalFormConstraints.text}
            {...view.register("text")}
          />

          <FieldError message={view.errors.text?.message} />

          <Button
            size="medium"
            stretched
            loading={view.isSending}
            disabled={view.isSending}
            onClick={view.send}
          >
            Отправить предложение
          </Button>

          {view.sendError !== null && (
            <Typography.Text className={styles.Error} variant="description">
              {errorMessage(
                view.sendError,
                "Предложение не отправилось. Проверьте связь и попробуйте ещё раз.",
              )}
            </Typography.Text>
          )}
        </>
      )}

      {!view.isChairman && view.mine.length > 0 && (
        <Typography.Text variant="body-strong" color="primary">
          Мои предложения
        </Typography.Text>
      )}

      {!view.isChairman &&
        view.mine.map((proposal) => (
          <ProposalRow key={proposal.id} proposal={proposal} />
        ))}

      {view.isChairman && view.incoming.length === 0 && !view.isPending && (
        <Typography.Text variant="description" color="secondary">
          Соседи пока ничего не предложили. Их предложения придут сюда и в бота,
          без имени автора.
        </Typography.Text>
      )}

      {view.isChairman &&
        view.incoming.map((proposal) => (
          <ProposalRow
            key={proposal.id}
            proposal={proposal}
            actions={
              proposal.status === "new" && (
                <>
                  <Button
                    size="small"
                    disabled={answering.isPending}
                    onClick={() => answering.accept(proposal)}
                  >
                    Принять
                  </Button>

                  <Button
                    size="small"
                    variant="secondary"
                    disabled={answering.isPending}
                    onClick={() => answering.ask(proposal)}
                  >
                    Отклонить
                  </Button>

                  <Button
                    size="small"
                    variant="secondary"
                    onClick={() =>
                      void navigate(generatePath(Routes.MEETING_NEW), {
                        state: { proposalId: proposal.id, text: proposal.text },
                      })
                    }
                  >
                    Вынести на опрос
                  </Button>
                </>
              )
            }
          />
        ))}

      {view.loadError !== null && (
        <Typography.Text className={styles.Error} variant="description">
          {errorMessage(
            view.loadError,
            "Предложения не загрузились. Проверьте связь и попробуйте ещё раз.",
          )}
        </Typography.Text>
      )}

      <ConfirmDialog
        isOpen={answering.declining !== null}
        title="Отклонить предложение?"
        description={
          <>
            <Textarea
              rows={3}
              mode="secondary"
              placeholder="Объясните автору, почему"
              maxLength={proposalFormConstraints.answer}
              {...answering.register("answer")}
            />

            <FieldError message={answering.errors.answer?.message} />
          </>
        }
        confirmLabel="Отправить ответ"
        error={
          answering.error === null
            ? undefined
            : errorMessage(
                answering.error,
                "Ответ не отправился. Проверьте связь и попробуйте ещё раз.",
              )
        }
        isPending={answering.isPending}
        onConfirm={answering.decline}
        onClose={answering.dismiss}
      />
    </section>
  );
};
