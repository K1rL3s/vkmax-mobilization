import { useWatch } from "react-hook-form";
import { Flex } from "@maxhub/max-ui";

import { FieldError } from "@/shared/ui/field-error";

import { messageFormConstraints } from "../domain/message-form-constraints";
import { useRequestReply } from "../model/use-request-reply";

import { MessageComposer, type MessageComposerMode } from "./message-composer";

import styles from "./reply-form.module.css";

export const ReplyForm = ({
  requestId,
  mode,
}: {
  requestId: number;
  mode?: MessageComposerMode;
}) => {
  const model = useRequestReply(requestId);
  const text = useWatch({ control: model.form.control, name: "text" });
  const fieldError = model.form.formState.errors.text;

  return (
    <Flex asChild align="stretch" direction="column" gap={8}>
      <form className={styles.Reply} onSubmit={model.submit} noValidate>
        <MessageComposer
          field={model.form.register("text")}
          placeholder="Написать в УК"
          maxLength={messageFormConstraints.text}
          invalid={!!fieldError}
          canSend={text.trim().length > 0 && !model.isPending}
          mode={mode}
        />
        <FieldError message={fieldError?.message ?? model.error} />
      </form>
    </Flex>
  );
};
