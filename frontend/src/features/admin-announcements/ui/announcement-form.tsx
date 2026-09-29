import type { ReactNode } from "react";
import { Button, Flex, Panel, Textarea, Typography } from "@maxhub/max-ui";

import { FlatPicker, useIsOrgAdmin } from "@/features/admin-reception";
import { Card } from "@/shared/ui/card";
import { Checkbox } from "@/shared/ui/checkbox";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import { FieldError } from "@/shared/ui/field-error";
import { alertIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import { announcementFormConstraints } from "../domain/announcement-form-constraints";
import {
  addressees,
  channelsLabel,
  housesCount,
  scopeLabel,
} from "../domain/labels";
import { useAnnouncementForm } from "../model/use-announcement-form";
import type { OrgHouse } from "../model/use-announcements";

import { WorksFields } from "./works-fields";

import styles from "./announcement-form.module.css";

const Option = ({
  checked,
  onChange,
  label,
  caption,
  isWarning = false,
  disabled = false,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  caption?: ReactNode;
  isWarning?: boolean;
  disabled?: boolean;
}) => (
  <Checkbox checked={checked} disabled={disabled} onChange={onChange}>
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

const Chip = ({
  isPressed,
  onClick,
  children,
}: {
  isPressed: boolean;
  onClick: () => void;
  children: ReactNode;
}) => (
  <Button
    type="button"
    size="small"
    variant={isPressed ? "primary" : "secondary"}
    aria-pressed={isPressed}
    onClick={onClick}
  >
    {children}
  </Button>
);

export const AnnouncementForm = ({ houses }: { houses: OrgHouse[] }) => {
  const form = useAnnouncementForm(houses);
  const isAdmin = useIsOrgAdmin();
  const { textMax } = announcementFormConstraints;
  const house = form.scopeHouse;
  const hasEntrances = house !== undefined && house.entrances > 1;

  return (
    <Panel className={styles.Page} mode="secondary">
      <form className={styles.Form} noValidate onSubmit={form.submit}>
        <div className={styles.Content}>
          <Flex align="stretch" direction="column" gapY={4}>
            <Typography.Text asChild variant="header" color="primary">
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

          {house && (hasEntrances || isAdmin) && (
            <Flex asChild align="stretch" direction="column" gapY={8}>
              <section>
                <Typography.Text asChild variant="title" color="primary">
                  <h2>Кому в доме</h2>
                </Typography.Text>

                <div className={styles.Chips}>
                  <Chip
                    isPressed={form.scope === "house"}
                    onClick={() => form.setScope("house")}
                  >
                    Всему дому
                  </Chip>

                  {hasEntrances && (
                    <Chip
                      isPressed={form.scope === "entrances"}
                      onClick={() => form.setScope("entrances")}
                    >
                      Подъездам
                    </Chip>
                  )}

                  {isAdmin && (
                    <Chip
                      isPressed={form.scope === "flats"}
                      onClick={() => form.setScope("flats")}
                    >
                      Квартирам
                    </Chip>
                  )}
                </div>

                {form.scope === "entrances" && (
                  <Card>
                    <div className={styles.Chips}>
                      {Array.from(
                        { length: house.entrances },
                        (_, index) => index + 1,
                      ).map((entrance) => {
                        const isPicked = form.entrances.includes(entrance);

                        return (
                          <Chip
                            key={entrance}
                            isPressed={isPicked}
                            onClick={() =>
                              form.toggleEntrance(entrance, !isPicked)
                            }
                          >
                            Подъезд {entrance}
                          </Chip>
                        );
                      })}
                    </div>

                    <Typography.Text variant="description" color="secondary">
                      Придёт в личные сообщения только жителям выбранных
                      подъездов. Жители, которые не указали квартиру, его не
                      получат
                    </Typography.Text>
                  </Card>
                )}

                {form.scope === "flats" && (
                  <Card>
                    <FlatPicker
                      houseId={house.id}
                      flatsCount={house.flats_count}
                      selected={form.flats}
                      onToggle={form.toggleFlat}
                    />

                    <Typography.Text variant="description" color="secondary">
                      Придёт в личные сообщения только подтверждённым жителям
                      выбранных квартир. В чат дома не уходит
                    </Typography.Text>
                  </Card>
                )}

                <FieldError
                  message={
                    form.errors.entrances?.message ?? form.errors.flats?.message
                  }
                />
              </section>
            </Flex>
          )}

          <Flex asChild align="stretch" direction="column" gapY={8}>
            <section>
              <Typography.Text asChild variant="title" color="primary">
                <h2>Куда отправить</h2>
              </Typography.Text>

              <Card>
                {form.scope !== "flats" && (
                  <Option
                    checked={form.channels.includes("chat")}
                    onChange={(checked) => form.toggleChannel("chat", checked)}
                    label="Чат дома"
                  />
                )}

                <Option
                  checked={form.channels.includes("direct")}
                  disabled={form.scope !== "house"}
                  onChange={(checked) => form.toggleChannel("direct", checked)}
                  label="Личные сообщения"
                  caption={
                    form.scope === "house"
                      ? undefined
                      : "Адресное объявление всегда уходит в личные сообщения"
                  }
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
              caption="Для аварий и отключений"
            />
          </Card>

          <WorksFields form={form} />

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
              {[
                addressees(form.draft.houseIds, houses),
                scopeLabel({
                  entrances:
                    form.draft.scope === "entrances"
                      ? form.draft.entrances
                      : null,
                  flats_count:
                    form.draft.scope === "flats"
                      ? form.draft.flats.length
                      : null,
                }),
              ]
                .filter(Boolean)
                .join(", ")}
              . {channelsLabel(form.draft.channels)}.
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
