import { Button, Flex, Typography } from "@maxhub/max-ui";

import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { getWebApp, haptic } from "@/shared/lib/max";

import type { RequestCard } from "../domain/types";

import styles from "./share-panel.module.css";

export const SharePanel = ({ request }: { request: RequestCard }) => {
  const share = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/chat-card",
    {
      onSuccess: ({ posted, share_text, share_link }) => {
        haptic.success();
        if (!posted) {
          void getWebApp()
            ?.shareMaxContent({ text: share_text, link: share_link })
            .catch(() => undefined);
        }
      },
      onError: haptic.error,
    },
  );

  return (
    <div className={styles.Panel}>
      <Flex align="stretch" direction="column" gapY={2}>
        <Typography.Text variant="body-strong" color="primary">
          Рассказать соседям
        </Typography.Text>
        <Typography.Text variant="description" color="secondary">
          {share.data?.posted
            ? "Опубликовано в чате дома. Бот сам обновит статус в этом сообщении"
            : "Соседи увидят номер, категорию, статус и срок заявки, без квартиры и имени"}
        </Typography.Text>
      </Flex>

      {!share.data?.posted && (
        <Button
          size="medium"
          variant="secondary"
          stretched
          loading={share.isPending}
          onClick={() =>
            share.mutate({
              params: { ...authParams(), path: { request_id: request.id } },
            })
          }
        >
          Рассказать соседям
        </Button>
      )}
      {share.error && (
        <Typography.Text variant="description" className={styles.Failed}>
          {errorMessage(
            share.error,
            "Не получилось поделиться. Проверьте связь и попробуйте ещё раз",
          )}
        </Typography.Text>
      )}
    </div>
  );
};
