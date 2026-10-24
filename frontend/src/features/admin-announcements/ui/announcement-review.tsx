import { Button, Flex, Typography } from "@maxhub/max-ui";

import { BottomSheet } from "@/shared/ui/bottom-sheet";
import { ErrorState, LoadingState } from "@/shared/ui/state";

import type {
  AnnouncementDraft,
  AnnouncementFormModel,
} from "../model/use-announcement-form";
import { useAnnouncementReview } from "../model/use-announcement-review";
import type { OrgHouse } from "../model/use-announcements";

import styles from "./announcement-review.module.css";

type Review = ReturnType<typeof useAnnouncementReview>;

const Preview = ({ review }: { review: Review }) => {
  if (review.isLoading) {
    return <LoadingState />;
  }

  if (review.message === undefined) {
    return (
      <ErrorState
        title="Не получилось проверить объявление"
        error={review.error}
        onRetry={review.retry}
      />
    );
  }

  return (
    <Flex direction="column" align="stretch" gapY={12}>
      <Flex direction="column" align="flex-start" gapY={4}>
        <Typography.Text
          className={styles.Bubble}
          variant="body"
          color="primary"
        >
          {review.message}
        </Typography.Text>

        {review.hashtagNote && (
          <Typography.Text variant="detail" color="secondary">
            {review.hashtagNote}
          </Typography.Text>
        )}
      </Flex>

      <Flex direction="column" align="stretch" gapY={4}>
        {review.lines.map((line) => (
          <Typography.Text key={line} variant="description" color="primary">
            {line}
          </Typography.Text>
        ))}
      </Flex>
    </Flex>
  );
};

const ReviewContent = ({
  draft,
  form,
  houses,
}: {
  draft: AnnouncementDraft;
  form: AnnouncementFormModel;
  houses: OrgHouse[];
}) => {
  const review = useAnnouncementReview(draft, houses);

  return (
    <Flex direction="column" align="stretch" gapY={12}>
      <Typography.Text asChild variant="title" color="primary">
        <h2 className={styles.Title}>{review.title}</h2>
      </Typography.Text>

      <Typography.Text variant="description" color="secondary">
        {review.summary}
      </Typography.Text>

      <Preview review={review} />

      <Flex direction="column" align="stretch" gapY={4}>
        <Typography.Text variant="description" color="secondary">
          Сколько дошло на самом деле, покажет отчёт о доставке
        </Typography.Text>

        <Typography.Text variant="description" color="secondary">
          Отозвать отправленное объявление нельзя
        </Typography.Text>
      </Flex>

      {form.sendError && (
        <Typography.Text className={styles.Error} variant="description">
          {form.sendError}
        </Typography.Text>
      )}

      <Button
        type="button"
        size="large"
        stretched
        variant="destructive"
        disabled={!review.isReady}
        loading={form.isSending}
        onClick={form.send}
      >
        Отправить
      </Button>

      <Button
        type="button"
        size="large"
        stretched
        variant="secondary"
        disabled={form.isSending}
        onClick={form.dismiss}
      >
        Изменить
      </Button>
    </Flex>
  );
};

export const AnnouncementReview = ({
  form,
  houses,
}: {
  form: AnnouncementFormModel;
  houses: OrgHouse[];
}) => (
  <BottomSheet isOpen={form.draft !== undefined} onClose={form.dismiss}>
    {form.draft && (
      <ReviewContent draft={form.draft} form={form} houses={houses} />
    )}
  </BottomSheet>
);
