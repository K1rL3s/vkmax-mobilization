import { Button, Flex, Panel, Textarea, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { EmergencyCard, emergencyContact } from "@/features/emergency";
import { outageForCategory, outageTitle, useHouseCard } from "@/features/house";
import type { components } from "@/shared/api/schema/generated";
import { formatDayTime } from "@/shared/lib/format";
import { Routes } from "@/shared/model/routes";
import { useSession } from "@/shared/model/session";
import {
  ATTACHMENT_LIMIT,
  AttachmentPicker,
} from "@/shared/ui/attachment-picker";
import { Chevron } from "@/shared/ui/chevron";
import { alertIcon, Icon, wrenchIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { ErrorState, LoadingState } from "@/shared/ui/state";
import { StatusPill } from "@/shared/ui/status-pill";

import { CategoryChips } from "./category-chips";
import { CategoryInfo } from "./category-info";
import { PlaceChoice } from "./place-choice";
import { SimilarPanel } from "./similar-panel";
import { DESCRIPTION_LIMIT, useNewRequest } from "./use-new-request";

import styles from "./new-request.module.css";

const DANGER_HINTS: Record<components["schemas"]["DangerKind"], string> = {
  gas: "Похоже, пахнет газом: не включайте свет и приборы, выйдите из квартиры и звоните 104 или 112",
  fire: "Похоже на дым или пожар: звоните 112, уходите по лестнице, не на лифте",
  electric:
    "Похоже, искрит проводка: не трогайте ее, отключите автомат в щитке, если это безопасно, при дыме звоните 112",
  trapped:
    "Похоже, в лифте застряли люди: нажмите кнопку связи в кабине и звоните в аварийную службу, при угрозе здоровью - 112",
  flood_electric:
    "Вода попала на проводку: не подходите к щиту и розеткам, звоните в аварийную службу, при искрах - 112",
  llm: "Похоже на аварию: при угрозе жизни и здоровью звоните 112",
};

const NewRequestPage = () => {
  const form = useNewRequest();
  const { currentResidency: residency } = useSession();
  const house = useHouseCard(residency?.house_id);

  if (form.isCategoriesFailed) {
    return (
      <ErrorState
        fill
        error={form.categoriesError}
        onRetry={form.retryCategories}
      />
    );
  }

  if (form.categories.length === 0) {
    return <LoadingState fill title="Готовим форму" />;
  }

  const outage = outageForCategory(house.data?.outages ?? [], form.category);
  const selected = form.categories.find(
    ({ category }) => category === form.category,
  );

  return (
    <Panel className={styles.Page} mode="secondary">
      <div className={styles.Content}>
        {form.danger && (
          <EmergencyCard
            org={house.data?.org}
            hint={DANGER_HINTS[form.danger]}
          />
        )}

        {!form.isDispute &&
          form.description === "" &&
          form.attachments.attachments.length === 0 && (
            <Flex asChild align="center" gap={12}>
              <Link to={Routes.EMERGENCY} className={styles.Emergency}>
                <Icon src={alertIcon} className={styles.EmergencyIcon} />
                <Typography.Text variant="body-strong" className={styles.Grow}>
                  Авария? Сначала позвоните
                </Typography.Text>
                <Chevron />
              </Link>
            </Flex>
          )}

        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>{form.subject ?? "Что случилось?"}</h2>
            </Typography.Text>

            <Textarea
              className={styles.Description}
              mode="secondary"
              rows={4}
              placeholder={
                form.subject
                  ? "Что непонятно в этой строке? Например: почему выросло"
                  : "Опишите проблему своими словами: что, где и когда началось"
              }
              value={form.description}
              onChange={(event) => form.setDescription(event.target.value)}
            />

            <Typography.Text
              className={styles.Counter}
              variant="detail"
              color="secondary"
            >
              {form.description.length} / {DESCRIPTION_LIMIT}
            </Typography.Text>
          </section>
        </Flex>

        {!form.isDispute && (
          <Flex asChild align="stretch" direction="column" gap={8}>
            <section>
              <Typography.Text asChild variant="title" color="primary">
                <h2>Категория</h2>
              </Typography.Text>

              <CategoryChips
                categories={form.categories}
                value={form.category}
                suggested={form.suggested}
                onChange={form.setCategory}
              />
            </section>
          </Flex>
        )}

        {form.asksPlace && (
          <Flex asChild align="stretch" direction="column" gap={8}>
            <section>
              <Typography.Text asChild variant="title" color="primary">
                <h2>Где проблема?</h2>
              </Typography.Text>

              <PlaceChoice value={form.place} onChange={form.setPlace} />
            </section>
          </Flex>
        )}

        {selected && (
          <CategoryInfo
            category={selected}
            orgName={house.data?.org?.name ?? null}
            emergency={emergencyContact(house.data?.org)}
          />
        )}

        {outage && (
          <Flex direction="column" align="flex-start" gap={8}>
            <Typography.Text variant="description" color="secondary">
              По дому {outageTitle(outage).toLowerCase()}
            </Typography.Text>
            {outage.is_demo && (
              <StatusPill tone="themed">демо-данные</StatusPill>
            )}
          </Flex>
        )}

        {!form.isDispute && form.neighbours?.works && (
          <Flex asChild align="center" gap={12}>
            <Link to={Routes.ANNOUNCEMENTS} className={styles.Works}>
              <IconTile icon={wrenchIcon} tone="themed" />
              <Flex
                className={styles.Grow}
                align="stretch"
                direction="column"
                gapY={2}
              >
                <Typography.Text variant="body-strong" color="primary">
                  В доме идут плановые работы до{" "}
                  {formatDayTime(form.neighbours.works.ends_at)}
                </Typography.Text>
                <Typography.Text variant="description" color="secondary">
                  {form.neighbours.works.title}
                </Typography.Text>
              </Flex>
              <Chevron />
            </Link>
          </Flex>
        )}

        {!form.isDispute &&
          form.neighbours &&
          form.neighbours.neighbours_count > 0 && (
            <SimilarPanel
              count={form.neighbours.neighbours_count}
              canJoin={form.neighbours.can_join && form.canJoin}
              isJoining={form.isJoining}
              onJoin={() => form.submit(form.neighbours?.group_id)}
            />
          )}

        {form.isDispute ? (
          <Typography.Text variant="description" color="secondary">
            К заявке приложим расчёт и фото показаний за период
          </Typography.Text>
        ) : (
          <Flex asChild align="stretch" direction="column" gap={8}>
            <section>
              <Flex align="center" gap={8}>
                <Typography.Text
                  asChild
                  className={styles.Grow}
                  variant="title"
                  color="primary"
                >
                  <h2>Вложения</h2>
                </Typography.Text>
                <Typography.Text variant="description" color="secondary">
                  необязательно
                </Typography.Text>
              </Flex>

              <AttachmentPicker
                attachments={form.attachments.attachments}
                isFull={form.attachments.isFull}
                isUploading={form.attachments.isUploading}
                onAdd={form.attachments.add}
                onRemove={form.attachments.remove}
              />

              <Typography.Text
                variant="description"
                color="secondary"
                className={form.attachments.error ? styles.Failed : undefined}
              >
                {form.attachments.error ??
                  `До ${ATTACHMENT_LIMIT} файлов, из них до 2 видео. Видео до 50 МБ и 60 секунд`}
              </Typography.Text>
            </section>
          </Flex>
        )}

        {form.error && (
          <Typography.Text variant="description" className={styles.Failed}>
            {form.error}
          </Typography.Text>
        )}
      </div>

      <div className={styles.Footer}>
        {form.missing && (
          <Typography.Text
            className={styles.Missing}
            variant="description"
            color="secondary"
          >
            {form.missing}
          </Typography.Text>
        )}

        <Button
          size="large"
          stretched
          loading={form.isSending}
          disabled={!form.canSubmit}
          onClick={() => form.submit()}
        >
          Отправить заявку
        </Button>
      </div>
    </Panel>
  );
};

export const Component = NewRequestPage;
