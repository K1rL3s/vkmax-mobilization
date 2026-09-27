import { Flex, Typography } from "@maxhub/max-ui";

import type { RequestCard } from "../domain/types";

import styles from "./request-photos.module.css";

export const RequestPhotos = ({
  title,
  files,
}: {
  title: string;
  files: RequestCard["photos"];
}) => {
  if (files.length === 0) return null;

  return (
    <Flex asChild align="stretch" direction="column" gap={8}>
      <section>
        <Typography.Text asChild variant="title" color="primary">
          <h2>{title}</h2>
        </Typography.Text>
        <div className={styles.Photos}>
          {files.map((file, index) => (
            <a key={file.name} href={file.url} target="_blank" rel="noreferrer">
              <img
                src={file.url}
                alt={`${title}, ${index + 1}`}
                width={144}
                height={144}
                loading="lazy"
              />
            </a>
          ))}
        </div>
      </section>
    </Flex>
  );
};
