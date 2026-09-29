import { Flex, Typography } from "@maxhub/max-ui";

import type { RequestAttachment } from "../domain/types";

import styles from "./request-attachments.module.css";

export const RequestAttachments = ({
  title,
  attachments,
}: {
  title: string;
  attachments: RequestAttachment[];
}) => {
  if (attachments.length === 0) return null;

  return (
    <Flex asChild align="stretch" direction="column" gap={8}>
      <section>
        <Typography.Text asChild variant="title" color="primary">
          <h2>{title}</h2>
        </Typography.Text>
        <div className={styles.Attachments}>
          {attachments.map((file, index) =>
            file.is_video ? (
              <video
                key={file.name}
                className={styles.Video}
                src={file.url}
                controls
                playsInline
                preload="metadata"
                aria-label={`${title}, видео ${index + 1}`}
              />
            ) : (
              <a
                key={file.name}
                href={file.url}
                target="_blank"
                rel="noreferrer"
              >
                <img
                  src={file.url}
                  alt={`${title}, ${index + 1}`}
                  width={144}
                  height={144}
                  loading="lazy"
                />
              </a>
            ),
          )}
        </div>
      </section>
    </Flex>
  );
};
