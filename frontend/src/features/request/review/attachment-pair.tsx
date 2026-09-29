import { Flex, Typography } from "@maxhub/max-ui";

import { cameraIcon, Icon } from "@/shared/ui/icon";

import { formatDay } from "@/shared/lib/format";
import type { RequestAttachment, RequestCard } from "../domain/types";

import styles from "./attachment-pair.module.css";

type ShotProps = {
  title: string;
  caption: string;
  attachments: RequestAttachment[];
};

const Shot = ({ title, caption, attachments }: ShotProps) => {
  const rest = attachments.length - 1;

  return (
    <Flex align="stretch" direction="column" gapY={4}>
      <div className={styles.Tile}>
        {attachments[0] ? (
          attachments[0].is_video ? (
            <video
              src={attachments[0].url}
              controls
              playsInline
              preload="metadata"
            />
          ) : (
            <img src={attachments[0].url} alt={attachments[0].name} />
          )
        ) : (
          <Icon src={cameraIcon} size={28} className={styles.Empty} />
        )}
      </div>
      <Typography.Text variant="body-strong" color="primary">
        {title}
      </Typography.Text>
      <Typography.Text variant="description" color="secondary">
        {attachments.length > 0 ? caption : "Вложений нет"}
        {rest > 0 && ` · ещё ${rest}`}
      </Typography.Text>
    </Flex>
  );
};

export const AttachmentPair = ({
  request,
  doneAt,
}: {
  request: RequestCard;
  doneAt: string | null;
}) => (
  <div className={styles.Pair}>
    <Shot
      title="Было"
      caption={`Ваше · ${formatDay(request.created_at)}`}
      attachments={request.photos}
    />
    <Shot
      title="Стало"
      caption={`Исполнителя${doneAt ? ` · ${formatDay(doneAt)}` : ""}`}
      attachments={request.result_photos}
    />
  </div>
);
