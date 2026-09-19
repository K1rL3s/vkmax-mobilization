import { Button, Flex, Panel, Textarea, Typography } from "@maxhub/max-ui";

import { useHouseCard } from "@/features/house";
import { useSession } from "@/shared/model/session";
import { ErrorState, LoadingState } from "@/shared/ui/state";

import { DESCRIPTION_LIMIT, useNewRequest } from "./model/use-new-request";
import { PHOTO_LIMIT } from "./model/use-photos";
import { CategoryChips } from "./ui/category-chips";
import { CategoryInfo } from "./ui/category-info";
import { PhotoPicker } from "./ui/photo-picker";
import { SimilarPanel } from "./ui/similar-panel";

import styles from "./new-request.module.css";

const NewRequestPage = () => {
  const form = useNewRequest();
  const { currentResidency: residency } = useSession();
  const house = useHouseCard(residency?.house_id);

  if (form.categories.length === 0 && !form.isCategoriesFailed) {
    return <LoadingState fill title="Готовим форму" />;
  }

  if (form.isCategoriesFailed) {
    return <ErrorState fill onRetry={() => window.location.reload()} />;
  }

  const selected = form.categories.find(
    ({ category }) => category === form.category,
  );

  return (
    <Panel className={styles.Page} mode="secondary">
      <div className={styles.Content}>
        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>Что случилось?</h2>
            </Typography.Text>

            <Textarea
              className={styles.Description}
              rows={4}
              placeholder="Опишите проблему своими словами: что, где и когда началось"
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

        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>Категория</h2>
            </Typography.Text>

            <CategoryChips
              categories={form.categories}
              value={form.category}
              onChange={form.setCategory}
            />
          </section>
        </Flex>

        {selected && (
          <CategoryInfo
            category={selected}
            orgName={house.data?.org?.name ?? null}
          />
        )}

        {form.neighbours && form.neighbours.neighbours_count > 0 && (
          <SimilarPanel
            count={form.neighbours.neighbours_count}
            canJoin={form.neighbours.can_join && form.canSubmit}
            isJoining={form.isSubmitting}
            onJoin={() => form.submit(form.neighbours?.group_id ?? undefined)}
          />
        )}

        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Flex align="center" gap={8}>
              <Typography.Text
                asChild
                className={styles.Grow}
                variant="title"
                color="primary"
              >
                <h2>Фото</h2>
              </Typography.Text>
              <Typography.Text variant="description" color="secondary">
                необязательно
              </Typography.Text>
            </Flex>

            <PhotoPicker
              photos={form.photos.photos}
              isFull={form.photos.isFull}
              isUploading={form.photos.isUploading}
              onAdd={form.photos.add}
              onRemove={form.photos.remove}
            />

            <Typography.Text variant="description" color="secondary">
              {form.photos.isFailed
                ? "Фото не загрузилось, попробуйте ещё раз"
                : `До ${PHOTO_LIMIT} фото - так УК быстрее разберётся`}
            </Typography.Text>
          </section>
        </Flex>

        {form.isFailed && (
          <Typography.Text variant="description" className={styles.Failed}>
            Заявка не ушла. Проверьте связь и попробуйте ещё раз.
          </Typography.Text>
        )}
      </div>

      <div className={styles.Footer}>
        <Button
          size="large"
          stretched
          loading={form.isSubmitting}
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
