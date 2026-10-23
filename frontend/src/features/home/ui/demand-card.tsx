import { useState } from "react";
import { Button, Flex, Textarea, Typography } from "@maxhub/max-ui";
import { useBoolean, useCopy } from "@siberiacancode/reactuse";

import type { HouseCard } from "@/features/house";
import { Card } from "@/shared/ui/card";
import { FieldError } from "@/shared/ui/field-error";
import { alertIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import { ukLetter, ukMailto } from "../domain/uk-letter";
import { useUkInvite } from "../model/use-uk-invite";

import styles from "./demand-card.module.css";

type DemandCardProps = {
  house: HouseCard;
  flat: string | null | undefined;
  onSent: () => void;
};

export const DemandCard = ({ house, flat, onSent }: DemandCardProps) => {
  const { org } = house;
  const invite = useUkInvite(house, onSent);
  const [writing, write] = useBoolean();
  const [text, setText] = useState("");
  const copy = useCopy(2000);
  const letter = org
    ? ukLetter(org, house.address, flat, text, invite.inviteLink)
    : null;

  return (
    <Flex asChild align="stretch" direction="column" gap={12}>
      <Card>
        <Flex align="center" gap={12}>
          <IconTile icon={alertIcon} tone="neutral" />
          <Flex
            className={styles.Grow}
            align="stretch"
            direction="column"
            gapY={2}
          >
            <Typography.Text variant="body-strong" color="primary">
              УК пока не подключена к сервису
            </Typography.Text>
            <Typography.Text variant="description" color="secondary">
              Заявки и показания счётчиков станут доступны, когда управляющая
              компания подключится. Пока можно связаться с ней напрямую
            </Typography.Text>
          </Flex>
        </Flex>

        {house.demand_sent ? (
          <>
            <Typography.Text variant="description" color="secondary">
              {invite.status}
            </Typography.Text>
            {invite.resend && (
              <Button
                size="medium"
                variant="secondary"
                stretched
                onClick={invite.resend}
              >
                Отправить приглашение ещё раз
              </Button>
            )}
          </>
        ) : (
          <Button
            size="medium"
            stretched
            loading={invite.isCalling}
            onClick={invite.call}
          >
            {org ? "Позвать УК в Жэку" : "Хочу Жэку в доме"}
          </Button>
        )}

        {org && letter && !writing && (
          <>
            <Typography.Text variant="description" color="secondary">
              Соберём письмо в УК с вашим текстом, а отправите его вы сами
            </Typography.Text>
            <Button
              size="medium"
              variant="secondary"
              stretched
              onClick={() => write(true)}
            >
              Написать в УК
            </Button>
          </>
        )}

        {org && letter && writing && (
          <>
            <Textarea
              rows={4}
              mode="secondary"
              placeholder="Что случилось"
              maxLength={1000}
              value={text}
              onChange={(event) => setText(event.target.value)}
            />

            <Typography.Text asChild variant="description" color="primary">
              <pre className={styles.Letter}>{letter.body}</pre>
            </Typography.Text>

            {org.email ? (
              <>
                <Button asChild size="medium" stretched>
                  <a href={ukMailto(org.email, letter)}>Открыть почту</a>
                </Button>
                <Typography.Text variant="description" color="secondary">
                  Письмо уйдёт с вашего адреса на {org.email}. Если почта не
                  открылась, скопируйте текст
                </Typography.Text>
              </>
            ) : (
              <Typography.Text variant="description" color="secondary">
                В реестре нет почты УК. Отправьте текст письмом или отнесите на
                приём{org.address && `: ${org.address}`}
              </Typography.Text>
            )}

            <Button
              size="medium"
              variant="secondary"
              stretched
              onClick={() => void copy.copy(letter.body)}
            >
              {copy.copied ? "Текст скопирован" : "Скопировать текст"}
            </Button>
          </>
        )}

        {invite.error && <FieldError message={invite.error} />}
      </Card>
    </Flex>
  );
};
