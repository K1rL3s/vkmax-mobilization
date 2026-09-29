import { Button, Flex, Typography } from "@maxhub/max-ui";
import { useCopy } from "@siberiacancode/reactuse";

import { authParams } from "@/shared/api/instance";
import { errorMessage } from "@/shared/api/errors";
import { duration, formatDayTime } from "@/shared/lib/format";
import { getWebApp } from "@/shared/lib/max";
import { BottomSheet } from "@/shared/ui/bottom-sheet";

import {
  useChairmanHandover,
  useIssueHandover,
  useRevokeHandover,
} from "./use-chairman-handover";

import styles from "./handover-dialog.module.css";

const HOUR = 60 * 60 * 1000;

const timeLeft = (expiresAt: string) =>
  duration(
    Math.max(Math.round((Date.parse(expiresAt) - Date.now()) / HOUR) * HOUR, 0),
  );

type HandoverDialogProps = {
  houseId: number;
  address: string;
  isOpen: boolean;
  onClose: () => void;
};

export const HandoverDialog = ({
  houseId,
  address,
  isOpen,
  onClose,
}: HandoverDialogProps) => {
  const link = useCopy(2000);
  const webApp = getWebApp();
  const handover = useChairmanHandover(houseId, isOpen);
  const issue = useIssueHandover(houseId);
  const revoke = useRevokeHandover(houseId);

  const busy = issue.isPending || revoke.isPending;
  const failure = issue.error ?? revoke.error;
  const live = handover.data ?? null;

  return (
    <BottomSheet isOpen={isOpen} onClose={onClose}>
      <Flex direction="column" align="stretch" gapY={16}>
        <Flex direction="column" gapY={4}>
          <Typography.Text asChild variant="title" color="primary">
            <h2 className={styles.Title}>Передать роль председателя</h2>
          </Typography.Text>
          <Typography.Text variant="description" color="secondary">
            Отправьте ссылку соседу-собственнику с подтверждённой квартирой в
            доме {address}. Роль перейдёт к нему, когда он откроет ссылку и
            нажмёт «Принять»
          </Typography.Text>
        </Flex>

        <Typography.Text variant="description" color="secondary">
          Председателя совета дома избирает общее собрание собственников: ссылка
          передаёт права в приложении и не заменяет протокол собрания
        </Typography.Text>

        {live && (
          <Flex
            className={styles.Link}
            direction="column"
            align="stretch"
            gapY={12}
          >
            <Flex direction="column" gapY={2}>
              <Typography.Text variant="description" color="secondary">
                Ссылка для нового председателя
              </Typography.Text>
              <span className={styles.Code}>{live.code}</span>
            </Flex>

            <Flex align="center" gap={8} wrap="wrap">
              <Button
                size="small"
                variant="secondary"
                onClick={() => void link.copy(live.deeplink)}
              >
                {link.copied ? "Скопировано" : "Скопировать"}
              </Button>
              <Button
                size="small"
                variant="secondary"
                disabled={!webApp}
                onClick={() =>
                  void webApp
                    ?.shareMaxContent({
                      text: "Предлагаю вам стать председателем совета нашего дома",
                      link: live.deeplink,
                    })
                    .catch(() => undefined)
                }
              >
                Поделиться
              </Button>
            </Flex>

            <Flex direction="column" gapY={2}>
              <Typography.Text variant="description" color="secondary">
                Действует до
              </Typography.Text>
              <Typography.Text variant="body-strong" color="primary">
                {formatDayTime(live.expires_at)}
              </Typography.Text>
              <Typography.Text variant="description" color="secondary">
                ещё {timeLeft(live.expires_at)}
              </Typography.Text>
            </Flex>

            {link.copied && (
              <Typography.Text variant="description" color="secondary">
                Ссылка скопирована, отправьте её соседу
              </Typography.Text>
            )}
          </Flex>
        )}

        {failure && (
          <Typography.Text className={styles.Error} variant="description">
            {errorMessage(failure, "Не получилось. Попробуйте ещё раз")}
          </Typography.Text>
        )}

        <Flex direction="column" align="stretch" gapY={8}>
          <Button
            size="large"
            stretched
            loading={issue.isPending}
            disabled={busy || handover.isLoading}
            onClick={() =>
              issue.mutate({
                params: { ...authParams(), path: { house_id: houseId } },
              })
            }
          >
            {live ? "Выдать новую ссылку" : "Создать ссылку"}
          </Button>
          {live && (
            <Button
              size="large"
              stretched
              variant="secondary"
              loading={revoke.isPending}
              disabled={busy}
              onClick={() =>
                revoke.mutate({
                  params: { ...authParams(), path: { house_id: houseId } },
                })
              }
            >
              Отозвать ссылку
            </Button>
          )}
          <Button
            size="large"
            stretched
            variant="secondary"
            disabled={busy}
            onClick={onClose}
          >
            Закрыть
          </Button>
        </Flex>
      </Flex>
    </BottomSheet>
  );
};
