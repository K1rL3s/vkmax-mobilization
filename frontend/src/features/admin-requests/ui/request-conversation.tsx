import { useWatch } from "react-hook-form";
import { Flex, Switch, Typography } from "@maxhub/max-ui";

import { MessageComposer, MessageThread } from "@/features/request";
import { FieldError } from "@/shared/ui/field-error";

import { requestFormConstraints } from "../domain/request-form-constraints";
import type { AdminRequest } from "../domain/request-workflow";
import { useRequestReplyForm } from "../model/use-request-reply-form";

import styles from "./request-conversation.module.css";

export const RequestConversation = ({ request }: { request: AdminRequest }) => {
  const model = useRequestReplyForm(request.id);
  const { form } = model;
  const [text, question] = useWatch({
    control: form.control,
    name: ["text", "question"],
  });
  const canAsk = request.author_name != null && request.status !== "done";
  const fieldError = form.formState.errors.text;

  return (
    <Flex asChild align="stretch" direction="column" gap={8}>
      <section>
        <Typography.Text asChild variant="title" color="primary">
          <h2>Переписка с жителем</h2>
        </Typography.Text>

        <MessageThread messages={request.messages} />

        <Flex asChild align="stretch" direction="column" gap={8}>
          <form className={styles.Reply} onSubmit={model.submit} noValidate>
            {canAsk && (
              <label className={styles.Switch}>
                <Typography.Text variant="body" color="primary">
                  Нужен ответ жителя
                </Typography.Text>
                <Switch type="checkbox" {...form.register("question")} />
              </label>
            )}
            {request.author_name == null && (
              <Typography.Text variant="description" color="secondary">
                У заявки нет привязанного жителя. Ответ сохранится в истории,
                уведомление в MAX не отправится.
              </Typography.Text>
            )}
            {canAsk && question && (
              <Typography.Text variant="description" color="secondary">
                Житель получит вопрос в MAX с кнопкой «✍️ Ответить», а заявка
                будет ждать его ответа.
              </Typography.Text>
            )}
            <MessageComposer
              field={form.register("text")}
              placeholder="Ответ жителю"
              maxLength={requestFormConstraints.reply}
              invalid={!!fieldError}
              canSend={text.trim().length > 0}
            />
            <FieldError message={fieldError?.message ?? model.error} />
          </form>
        </Flex>
      </section>
    </Flex>
  );
};
