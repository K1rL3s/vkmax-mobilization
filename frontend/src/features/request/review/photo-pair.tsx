import { Flex, Typography } from "@maxhub/max-ui";

import { cameraIcon, Icon } from "@/shared/ui/icon";

import { formatDay } from "@/shared/lib/format";
import type { RequestCard } from "../domain/types";

import styles from "./photo-pair.module.css";

type ShotProps = {
  title: string;
  caption: string;
  photos: RequestCard["photos"];
};

const Shot = ({ title, caption, photos }: ShotProps) => {
  const rest = photos.length - 1;

  return (
    <Flex align="stretch" direction="column" gapY={4}>
      <div className={styles.Tile}>
        {photos[0] ? (
          <img src={photos[0].url} alt={photos[0].name} />
        ) : (
          <Icon src={cameraIcon} size={28} className={styles.Empty} />
        )}
      </div>
      <Typography.Text variant="body-strong" color="primary">
        {title}
      </Typography.Text>
      <Typography.Text variant="description" color="secondary">
        {photos.length > 0 ? caption : "Фото нет"}
        {rest > 0 && ` · ещё ${rest}`}
      </Typography.Text>
    </Flex>
  );
};

export const PhotoPair = ({
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
      photos={request.photos}
    />
    <Shot
      title="Стало"
      caption={`Исполнителя${doneAt ? ` · ${formatDay(doneAt)}` : ""}`}
      photos={request.result_photos}
    />
  </div>
);
