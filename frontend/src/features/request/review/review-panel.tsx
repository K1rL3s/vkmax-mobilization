import { Button, Flex, Textarea, Typography } from "@maxhub/max-ui";

import { duration, formatDayTime } from "@/shared/lib/format";
import { AttachmentPicker } from "@/shared/ui/attachment-picker";
import { autoClose } from "../domain/timeline";
import type { RequestCard } from "../domain/types";

import { AttachmentPair } from "./attachment-pair";
import { COMMENT_LIMIT, useReview } from "./use-review";

import styles from "./review-panel.module.css";

export const ReviewPanel = ({ request }: { request: RequestCard }) => {
  const form = useReview(request);
  const closing = autoClose(request);

  return (
    <div className={styles.Panel}>
      <Flex align="center" gap={8}>
        <Typography.Text
          className={styles.Grow}
          variant="body-strong"
          color="primary"
        >
          Проверьте работу
        </Typography.Text>
        {closing !== null && closing.left > 0 && (
          <Typography.Text className={styles.Left} variant="description">
            осталось {duration(closing.left)}
          </Typography.Text>
        )}
      </Flex>

      {closing !== null && (
        <>
          <div className={styles.Track}>
            <div
              className={styles.Fill}
              style={{ width: `${closing.progress * 100}%` }}
            />
          </div>
          <Typography.Text variant="description" color="secondary">
            Без ответа заявка закроется как выполненная{" "}
            {formatDayTime(closing.at)}
          </Typography.Text>
        </>
      )}

      <AttachmentPair request={request} doneAt={closing?.sentAt ?? null} />

      <Flex align="stretch" direction="column" gapY={4}>
        <Textarea
          className={styles.Comment}
          mode="secondary"
          rows={2}
          placeholder="Что не так с работой"
          value={form.comment}
          onChange={(event) => form.setComment(event.target.value)}
        />
        <Typography.Text
          className={styles.Counter}
          variant="detail"
          color="secondary"
        >
          {form.comment.length} / {COMMENT_LIMIT}
        </Typography.Text>
      </Flex>

      <Flex align="stretch" direction="column" gapY={8}>
        <AttachmentPicker
          attachments={form.attachments.attachments}
          isFull={form.attachments.isFull}
          isUploading={form.attachments.isUploading}
          onAdd={form.attachments.add}
          onRemove={form.attachments.remove}
        />
        <Typography.Text
          variant="description"
          color="secondary"
          className={form.attachments.error ? styles.Failed : undefined}
        >
          {form.attachments.error ??
            (request.rejection_needs_photo
              ? "Приложите фото того, что не так"
              : "Приложите фото, если есть")}
        </Typography.Text>
      </Flex>

      {form.error && (
        <Typography.Text variant="description" className={styles.Failed}>
          {form.error}
        </Typography.Text>
      )}

      <Flex direction="row-reverse" wrap="wrap" gap={8}>
        <Button
          className={styles.Action}
          size="large"
          loading={form.isAccepting}
          disabled={!form.canAccept}
          onClick={form.accept}
        >
          Принять
        </Button>
        <Button
          className={styles.Action}
          size="large"
          variant="secondary"
          loading={form.isRejecting}
          disabled={!form.canReject}
          onClick={form.reject}
        >
          Сделано плохо
        </Button>
      </Flex>

      <Typography.Text variant="detail" color="secondary">
        «Сделано плохо» создаст повторную заявку со ссылкой на эту
      </Typography.Text>
    </div>
  );
};
