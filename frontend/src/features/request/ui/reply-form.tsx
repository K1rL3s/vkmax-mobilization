import { Button, Flex, Textarea } from "@maxhub/max-ui";

import { FieldError } from "@/shared/ui/field-error";

import { messageFormConstraints } from "../domain/message-form-constraints";
import { useRequestReply } from "../model/use-request-reply";

export const ReplyForm = ({ requestId }: { requestId: number }) => {
  const model = useRequestReply(requestId);
  const fieldError = model.form.formState.errors.text;

  return (
    <Flex asChild align="stretch" direction="column" gap={8}>
      <form onSubmit={model.submit} noValidate>
        <Textarea
          mode="secondary"
          rows={3}
          maxLength={messageFormConstraints.text}
          autoComplete="off"
          placeholder="Написать в УК"
          aria-label="Написать в УК"
          {...model.form.register("text")}
          disabled={model.isPending}
          aria-invalid={!!fieldError}
        />
        <FieldError message={fieldError?.message ?? model.error} />
        <Button type="submit" size="large" stretched loading={model.isPending}>
          Отправить
        </Button>
      </form>
    </Flex>
  );
};
