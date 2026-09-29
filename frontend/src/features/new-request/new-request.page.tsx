import { Button, Flex, Panel, Textarea, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { emergencyContact } from "@/features/emergency";
import { outageForCategory, outageTitle, useHouseCard } from "@/features/house";
import { Routes } from "@/shared/model/routes";
import { useSession } from "@/shared/model/session";
import {
  ATTACHMENT_LIMIT,
  AttachmentPicker,
} from "@/shared/ui/attachment-picker";
import { Chevron } from "@/shared/ui/chevron";
import { alertIcon, Icon } from "@/shared/ui/icon";
import { ErrorState, LoadingState } from "@/shared/ui/state";
import { StatusPill } from "@/shared/ui/status-pill";

import { CategoryChips } from "./category-chips";
import { CategoryInfo } from "./category-info";
import { SimilarPanel } from "./similar-panel";
import { DESCRIPTION_LIMIT, useNewRequest } from "./use-new-request";

import styles from "./new-request.module.css";

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

        {selected && (
          <CategoryInfo
            category={selected}
            orgName={house.data?.org?.name ?? null}
            emergency={emergencyContact(house.data?.org)}
          />
        )}

        {outage && (
          <Flex direction="column" align="flex-start" gap={6}>
            <Typography.Text variant="description" color="secondary">
              По дому {outageTitle(outage).toLowerCase()}
            </Typography.Text>
            {outage.is_demo && (
              <StatusPill tone="themed">демо-данные</StatusPill>
            )}
          </Flex>
        )}

        {!form.isDispute &&
          form.neighbours &&
          form.neighbours.neighbours_count > 0 && (
            <SimilarPanel
              count={form.neighbours.neighbours_count}
              canJoin={form.neighbours.can_join && form.canSubmit}
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
