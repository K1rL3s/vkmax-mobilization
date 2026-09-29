import { Button, Flex, Typography } from "@maxhub/max-ui";
import { useCopy } from "@siberiacancode/reactuse";

import { useHouseCard } from "@/features/house";
import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { formatShortDay, formatTime, telHref } from "@/shared/lib/format";
import { Chevron } from "@/shared/ui/chevron";

import { gjiAppeal } from "../domain/gji";
import { complaintRecipients } from "../domain/recipients";
import type { RequestCard } from "../domain/types";
import { refetchRequests } from "../model/use-repeat-request";

import styles from "./escalation-panel.module.css";

export const EscalationPanel = ({ request }: { request: RequestCard }) => {
  const house = useHouseCard(request.house_id);
  const copy = useCopy(2000);
  const escalate = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/escalate",
    { onSuccess: refetchRequests },
  );
  const pdf = rqClient.useMutation(
    "post",
    "/api/requests/{request_id}/gji-pdf",
  );

  const text = house.data ? gjiAppeal(request, house.data) : null;
  const gzhi = house.data?.services.find((service) => service.kind === "gzhi");

  return (
    <div className={styles.Panel}>
      <Flex align="stretch" direction="column" gapY={2}>
        <Typography.Text variant="body-strong" color="primary">
          1. Попросить руководство УК
        </Typography.Text>
        <Typography.Text variant="description" color="secondary">
          {request.escalated_at
            ? `Руководство УК уведомлено ${formatShortDay(request.escalated_at)} в ${formatTime(request.escalated_at)}`
            : "Руководство УК получит сообщение, а заявка встанет первой в списке УК"}
        </Typography.Text>
      </Flex>

      {!request.escalated_at && (
        <Button
          size="medium"
          stretched
          loading={escalate.isPending}
          onClick={() =>
            escalate.mutate({
              params: { ...authParams(), path: { request_id: request.id } },
            })
          }
        >
          Попросить руководство УК
        </Button>
      )}
      {escalate.error && (
        <Typography.Text variant="description" className={styles.Failed}>
          {errorMessage(
            escalate.error,
            "Не получилось отправить. Проверьте связь и попробуйте ещё раз",
          )}
        </Typography.Text>
      )}

      <Flex align="stretch" direction="column" gapY={2}>
        <Typography.Text variant="body-strong" color="primary">
          2. Жалоба в ГЖИ
        </Typography.Text>
        <Typography.Text variant="description" color="secondary">
          Бот пришлёт PDF: факты заявки, срок и его основание, история статусов
          и строки для подписей соседей. Впишите ФИО и адрес, распечатайте и
          подпишите
        </Typography.Text>
      </Flex>

      <Button
        size="medium"
        stretched
        loading={pdf.isPending}
        disabled={pdf.isSuccess}
        onClick={() =>
          pdf.mutate({
            params: { ...authParams(), path: { request_id: request.id } },
          })
        }
      >
        {pdf.isSuccess
          ? "Отправили в чат с ботом"
          : "Получить PDF в чат с ботом"}
      </Button>
      {pdf.error && (
        <Typography.Text variant="description" className={styles.Failed}>
          {errorMessage(
            pdf.error,
            "Не получилось отправить. Проверьте связь и попробуйте ещё раз",
          )}
        </Typography.Text>
      )}

      {text && (
        <>
          <Typography.Text variant="description" color="secondary">
            Или скопируйте текст и отправьте в жилищную инспекцию сами
          </Typography.Text>

          {gzhi && (
            <Typography.Text variant="description" color="secondary">
              {gzhi.name}:{" "}
              <a className={styles.Link} href={telHref(gzhi.phone)}>
                {gzhi.phone}
              </a>
              {gzhi.site && (
                <>
                  ,{" "}
                  <a
                    className={styles.Link}
                    href={gzhi.site}
                    target="_blank"
                    rel="noreferrer"
                  >
                    сайт инспекции
                  </a>
                </>
              )}
            </Typography.Text>
          )}

          <Typography.Text asChild variant="description" color="primary">
            <pre className={styles.Appeal}>{text}</pre>
          </Typography.Text>

          <Button
            size="medium"
            variant="secondary"
            stretched
            onClick={() => void copy.copy(text)}
          >
            {copy.copied ? "Текст скопирован" : "Скопировать текст"}
          </Button>
        </>
      )}

      <details className={styles.More}>
        <summary className={styles.MoreTitle}>
          <Typography.Text
            className={styles.Grow}
            variant="body-strong"
            color="primary"
          >
            3. Куда ещё
          </Typography.Text>
          <span className={styles.Chevron}>
            <Chevron />
          </span>
        </summary>
        <ul className={styles.Recipients}>
          {complaintRecipients(request.category).map((recipient) => (
            <li key={`${recipient.who} ${recipient.when}`}>
              <Typography.Text variant="body-strong" color="primary">
                {recipient.who} - {recipient.when}
              </Typography.Text>
              <Typography.Text variant="description" color="secondary">
                {recipient.how}
              </Typography.Text>
              {recipient.topics.length > 0 && (
                <Typography.Text variant="description" color="secondary">
                  {recipient.topics.length > 1 ? "Темы" : "Тема"} в ГИС ЖКХ:{" "}
                  {recipient.topics
                    .map(([code, name]) => `${code} «${name}»`)
                    .join(", ")}
                </Typography.Text>
              )}
            </li>
          ))}
        </ul>
        <Typography.Text
          className={styles.Source}
          variant="description"
          color="secondary"
        >
          Темы по справочнику НСИ 220 ГИС ЖКХ, сверено 29.09.2026
        </Typography.Text>
      </details>
    </div>
  );
};
