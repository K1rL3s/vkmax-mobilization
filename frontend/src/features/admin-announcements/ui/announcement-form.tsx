import type { ReactNode } from "react";
import { Button, Flex, Panel, Textarea, Typography } from "@maxhub/max-ui";

import { Card } from "@/shared/ui/card";
import { Checkbox } from "@/shared/ui/checkbox";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import { FieldError } from "@/shared/ui/field-error";
import { alertIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import { announcementFormConstraints } from "../domain/announcement-form-constraints";
import { addressees, channelsLabel, housesCount } from "../domain/labels";
import { useAnnouncementForm } from "../model/use-announcement-form";
import type { OrgHouse } from "../model/use-announcements";

import styles from "./announcement-form.module.css";

const Option = ({
  checked,
  onChange,
  label,
  caption,
  isWarning = false,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  caption?: ReactNode;
  isWarning?: boolean;
}) => (
  <Checkbox checked={checked} onChange={onChange}>
    <Flex align="stretch" direction="column" gapY={2}>
      <Typography.Text variant="body" color="primary">
        {label}
      </Typography.Text>

      {caption && (
        <Typography.Text
          className={isWarning ? styles.Error : undefined}
          variant="description"
          color={isWarning ? undefined : "secondary"}
        >
          {caption}
        </Typography.Text>
      )}
    </Flex>
  </Checkbox>
);

export const AnnouncementForm = ({ houses }: { houses: OrgHouse[] }) => {
  const form = useAnnouncementForm(houses);
  const { textMax } = announcementFormConstraints;

  return (
    <Panel className={styles.Page} mode="secondary">
      <form className={styles.Form} noValidate onSubmit={form.submit}>
        <div className={styles.Content}>
          <Flex align="stretch" direction="column" gapY={4}>
            <Typography.Text asChild variant="title" color="primary">
              <h1>Новое объявление</h1>
            </Typography.Text>

            <Typography.Text variant="description" color="secondary">
              Уйдёт жителям выбранных домов сразу после отправки
            </Typography.Text>
          </Flex>

          <Flex asChild align="stretch" direction="column" gapY={8}>
            <section>
              <Typography.Text asChild variant="title" color="primary">
                <h2>Текст</h2>
              </Typography.Text>

              <Textarea
                className={styles.Text}
                mode="secondary"
                rows={5}
                maxLength={textMax}
                placeholder="Что случилось или что будет, когда и что делать жителям"
                {...form.register("text")}
              />

              <Flex align="flex-start" gap={8}>
                <div className={styles.Grow}>
                  <FieldError message={form.errors.text?.message} />
                </div>

                <Typography.Text variant="detail" color="secondary">
                  {form.text.length} / {textMax}
                </Typography.Text>
              </Flex>
            </section>
          </Flex>

          <Flex asChild align="stretch" direction="column" gapY={8}>
            <section>
              <Typography.Text asChild variant="title" color="primary">
                <h2>Дома</h2>
              </Typography.Text>

              <Card>
                {houses.length > 1 && (
                  <Option
                    checked={form.isAllHouses}
                    onChange={form.toggleAllHouses}
                    label="Все дома"
                    caption={`${housesCount(houses.length)} в управлении организации`}
                  />
                )}

                {houses.map((house) => (
                  <Option
                    key={house.id}
                    checked={form.houseIds.includes(house.id)}
                    onChange={(checked) => form.toggleHouse(house.id, checked)}
                    label={house.address}
                    caption={house.chat_bound ? undefined : "Чат не привязан"}
                    isWarning
                  />
                ))}
              </Card>

              <FieldError message={form.errors.houseIds?.message} />
            </section>
          </Flex>

          <Flex asChild align="stretch" direction="column" gapY={8}>
            <section>
              <Typography.Text asChild variant="title" color="primary">
                <h2>Куда отправить</h2>
              </Typography.Text>

              <Card>
                <Option
                  checked={form.channels.includes("chat")}
                  onChange={(checked) => form.toggleChannel("chat", checked)}
                  label="Чат дома"
                  caption="Одно сообщение в чат, который бот привязал к дому"
                />

                <Option
                  checked={form.channels.includes("direct")}
                  onChange={(checked) => form.toggleChannel("direct", checked)}
                  label="Личные сообщения"
                  caption="Каждому жителю от бота. Для срочного: в обычных объявлениях создаёт дубль тем, кто состоит в чате"
                />
              </Card>

              <FieldError message={form.errors.channels?.message} />
            </section>
          </Flex>

          <Card>
            <Option
              checked={form.urgent}
              onChange={form.setUrgent}
              label="Срочное"
              caption="Для аварий и отключений. Житель увидит объявление выделенным, бот пришлёт его с заголовком «🚨 Срочное объявление». Куда отправить, решают галочки выше"
            />
          </Card>

          {form.withoutChat.length > 0 && (
            <Card>
              <Flex align="flex-start" gap={12}>
                <IconTile icon={alertIcon} tone="negative" />

                <Typography.Text variant="description" color="primary">
                  Без привязанного чата объявление не получат:{" "}
                  {form.withoutChat.map((house) => house.address).join("; ")}.
                  Добавьте личные сообщения или привяжите чат в карточке дома
                </Typography.Text>
              </Flex>
            </Card>
          )}
        </div>

        <div className={styles.Footer}>
          <Button type="submit" size="large" stretched>
            Отправить
          </Button>
        </div>
      </form>

      <ConfirmDialog
        isOpen={form.draft !== undefined}
        title={
          form.draft?.urgent
            ? "Отправить срочное объявление?"
            : "Отправить объявление?"
        }
        description={
          form.draft && (
            <>
              {addressees(form.draft.houseIds, houses)}.{" "}
              {channelsLabel(form.draft.channels)}.
              {form.withoutChat.length > 0 &&
                (form.withoutChat.length === form.draft.houseIds.length
                  ? " Ни у одного из этих домов нет привязанного чата, объявление никто не получит."
                  : ` Не получат дома без чата: ${form.withoutChat.map((house) => house.address).join("; ")}.`)}{" "}
              Отозвать отправленное объявление нельзя
            </>
          )
        }
        confirmLabel="Отправить"
        error={form.sendError}
        isPending={form.isSending}
        onConfirm={form.send}
        onClose={form.dismiss}
      />
    </Panel>
  );
};
