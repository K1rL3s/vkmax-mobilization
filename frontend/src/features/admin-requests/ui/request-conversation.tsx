import { useWatch } from "react-hook-form";
import { Flex, Spinner, Textarea, Typography } from "@maxhub/max-ui";

import { formatDayTime } from "@/shared/lib/format";
import { Card } from "@/shared/ui/card";
import { FieldError } from "@/shared/ui/field-error";
import { arrowUpIcon, Icon } from "@/shared/ui/icon";

import { requestFormConstraints } from "../domain/request-form-constraints";
import type { AdminRequest } from "../domain/request-workflow";
import { useRequestReplyForm } from "../model/use-request-reply-form";

import styles from "./request-conversation.module.css";

export const RequestConversation = ({ request }: { request: AdminRequest }) => {
  const model = useRequestReplyForm(request.id);
  const { form } = model;
  const text = useWatch({ control: form.control, name: "text" });
  const fieldError = form.formState.errors.text;

  return (
    <Flex asChild align="stretch" direction="column" gap={8}>
      <section>
        <Typography.Text asChild variant="title" color="primary">
          <h2>Переписка с жителем</h2>
        </Typography.Text>

        {request.messages.map((message, index) => (
          <Card key={`${message.created_at}-${index}`}>
            <Typography.Text variant="description" color="secondary">
              {message.author_name}
              {message.author_role === "staff"
                ? " · от сотрудника организации"
                : ""}{" "}
              · {formatDayTime(message.created_at)}
            </Typography.Text>
            <Typography.Text
              className={styles.Text}
              variant="body"
              color="primary"
            >
              {message.text}
            </Typography.Text>
          </Card>
        ))}

        <Flex asChild align="stretch" direction="column" gap={8}>
          <form onSubmit={model.submit} noValidate>
            <Typography.Text variant="description" color="secondary">
              {request.author_name == null
                ? "У заявки нет привязанного жителя. Ответ сохранится в истории, уведомление в MAX не отправится."
                : "Ответ придёт жителю в MAX с пометкой «от сотрудника организации»."}
            </Typography.Text>
            <div className={styles.Composer}>
              <Textarea
                mode="secondary"
                rows={3}
                maxLength={requestFormConstraints.reply}
                autoComplete="off"
                placeholder="Напишите, что сделано или когда ждать мастера…"
                {...form.register("text")}
                disabled={model.isPending}
                aria-invalid={!!fieldError}
                aria-label="Текст ответа"
              />
              {text.trim().length > 0 && (
                <button
                  className={styles.Send}
                  type="submit"
                  disabled={model.isPending}
                  aria-label="Отправить ответ"
                >
                  {model.isPending ? (
                    <Spinner size={20} />
                  ) : (
                    <Icon src={arrowUpIcon} size={20} />
                  )}
                </button>
              )}
            </div>
            <FieldError message={fieldError?.message ?? model.error} />
            {model.isSuccess && (
              <Typography.Text variant="description" role="status">
                Ответ сохранён в заявке.
              </Typography.Text>
            )}
          </form>
        </Flex>
      </section>
    </Flex>
  );
};
