import { Button, Flex, Typography } from "@maxhub/max-ui";
import { z } from "zod";

import { errorMessage } from "@/shared/api/errors";
import { authParams, rqClient } from "@/shared/api/instance";
import { getWebApp, haptic } from "@/shared/lib/max";
import { useSession } from "@/shared/model/session";

import styles from "./profile.module.css";

const contactSchema = z.object({
  phone: z.string().min(1).max(32),
  authDate: z.union([z.string(), z.number()]).transform(String),
  hash: z.string().min(1).max(128),
});

export const PhonePanel = () => {
  const { session, save } = useSession();
  const webApp = getWebApp();
  const onSuccess = (next: NonNullable<typeof session>) => {
    haptic.success();
    save(next);
  };
  const verify = rqClient.useMutation("post", "/api/me/phone", {
    onSuccess,
    onError: haptic.error,
  });
  const forget = rqClient.useMutation("delete", "/api/me/phone", {
    onSuccess,
  });
  const requestContact = webApp?.requestContact?.bind(webApp);

  if (!session || (!session.phone && !requestContact)) {
    return null;
  }

  const share = async () => {
    const contact = contactSchema.safeParse(
      await requestContact?.().catch(() => null),
    );
    if (!contact.success) {
      return;
    }
    verify.mutate({
      params: authParams(),
      body: {
        phone: contact.data.phone,
        auth_date: contact.data.authDate,
        hash: contact.data.hash,
      },
    });
  };

  const error = verify.error ?? forget.error;

  return (
    <Flex asChild align="stretch" direction="column" gap={8}>
      <section>
        <Typography.Text asChild variant="title" color="primary">
          <h2>Телефон для связи с УК</h2>
        </Typography.Text>
        <div className={styles.PhonePanel}>
          <Typography.Text variant="description" color="secondary">
            {session.phone
              ? `${session.phone}. Номер видят только сотрудники УК вашего дома, чтобы перезвонить по заявке`
              : "Номер из MAX подтверждается в одно касание. Его увидят только сотрудники УК вашего дома, чтобы перезвонить по заявке"}
          </Typography.Text>
          {session.phone ? (
            <Button
              size="medium"
              variant="secondary"
              stretched
              loading={forget.isPending}
              onClick={() => forget.mutate({ params: authParams() })}
            >
              Удалить номер
            </Button>
          ) : (
            <Button
              size="medium"
              stretched
              loading={verify.isPending}
              onClick={() => void share()}
            >
              Подтвердить номер из MAX
            </Button>
          )}
          {error && (
            <Typography.Text variant="description" className={styles.Failed}>
              {errorMessage(
                error,
                "Не получилось сохранить номер. Попробуйте ещё раз",
              )}
            </Typography.Text>
          )}
        </div>
      </section>
    </Flex>
  );
};
