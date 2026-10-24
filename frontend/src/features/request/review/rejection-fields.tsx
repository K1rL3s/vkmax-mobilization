import { useWatch } from "react-hook-form";
import { Flex, Textarea, Typography } from "@maxhub/max-ui";

import { AttachmentPicker } from "@/shared/ui/attachment-picker";
import { rejectionFormConstraints } from "../domain/rejection-form-constraints";

import type { Rejection } from "./use-rejection";

import styles from "./rejection-fields.module.css";

export const RejectionFields = ({ rejection }: { rejection: Rejection }) => {
  const comment = useWatch({
    control: rejection.form.control,
    name: "comment",
  });
  const { attachments } = rejection;

  return (
    <>
      <Flex align="stretch" direction="column" gapY={4}>
        <Textarea
          className={styles.Comment}
          mode="secondary"
          rows={2}
          placeholder="Что не так с работой"
          maxLength={rejectionFormConstraints.comment}
          aria-label="Что не так с работой"
          {...rejection.form.register("comment")}
        />
        <Typography.Text
          className={styles.Counter}
          variant="detail"
          color="secondary"
        >
          {`${comment.length} / ${rejectionFormConstraints.comment}`}
        </Typography.Text>
      </Flex>

      <Flex align="stretch" direction="column" gapY={8}>
        <AttachmentPicker
          attachments={attachments.attachments}
          isFull={attachments.isFull}
          isUploading={attachments.isUploading}
          onAdd={attachments.add}
          onRemove={attachments.remove}
        />
        <Typography.Text
          variant="description"
          color="secondary"
          className={attachments.error ? styles.Failed : undefined}
        >
          {attachments.error ?? photoHint(rejection.needsPhoto)}
        </Typography.Text>
      </Flex>
    </>
  );
};

const photoHint = (needsPhoto: boolean) =>
  needsPhoto ? "Приложите фото того, что не так" : "Приложите фото, если есть";
