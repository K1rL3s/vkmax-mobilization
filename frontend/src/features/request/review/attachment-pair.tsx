import { Flex, Typography } from "@maxhub/max-ui";

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
        {attachments[0]?.is_video ? (
          <video
            src={attachments[0].url}
            controls
            playsInline
            preload="metadata"
          />
        ) : (
          <img src={attachments[0]?.url} alt={attachments[0]?.name} />
        )}
      </div>
      <Typography.Text variant="body-strong" color="primary">
        {title}
      </Typography.Text>
      <Typography.Text variant="description" color="secondary">
        {caption}
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
}) => {
  const shots = [
    {
      title: "Было",
      caption: `Ваше · ${formatDay(request.created_at)}`,
      attachments: request.photos,
    },
    {
      title: "Стало",
      caption: `Исполнителя${doneAt ? ` · ${formatDay(doneAt)}` : ""}`,
      attachments: request.result_photos,
    },
  ].filter((shot) => shot.attachments.length > 0);

  if (shots.length === 0) return null;

  return (
    <div className={styles.Pair}>
      {shots.map((shot) => (
        <Shot key={shot.title} {...shot} />
      ))}
    </div>
  );
};
