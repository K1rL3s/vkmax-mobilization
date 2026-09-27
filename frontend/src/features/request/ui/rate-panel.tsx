import { Button, Flex, Textarea, Typography } from "@maxhub/max-ui";

import type { RequestCard } from "../domain/types";
import { FEEDBACK_LIMIT, useRatePanel } from "../model/use-rate-panel";

import { RatingStars } from "./rating-stars";

import styles from "./rate-panel.module.css";

export const RatePanel = ({ request }: { request: RequestCard }) => {
  const form = useRatePanel(request);

  if (!request.can_rate) {
    return (
      <div className={styles.Panel}>
        <Typography.Text variant="title" color="primary">
          Ваша оценка
        </Typography.Text>

        <RatingStars value={request.rating ?? 0} />

        {request.feedback && (
          <>
            <Typography.Text variant="description" color="secondary">
              {request.feedback}
            </Typography.Text>

            {form.repeatError && (
              <Typography.Text variant="description" className={styles.Failed}>
                {form.repeatError}
              </Typography.Text>
            )}

            <Button
              size="large"
              variant="secondary"
              loading={form.isRepeating}
              disabled={!form.canRepeat}
              onClick={form.repeat}
            >
              Проблема вернулась
            </Button>

            <Typography.Text variant="detail" color="secondary">
              Повторная заявка уйдёт с этим же текстом и ссылкой на эту
            </Typography.Text>
          </>
        )}
      </div>
    );
  }

  return (
    <div className={styles.Panel}>
      <Flex align="stretch" direction="column" gapY={2}>
        <Typography.Text variant="title" color="primary">
          Оцените работу
        </Typography.Text>
        <Typography.Text variant="description" color="secondary">
          Оценку увидит управляющая компания
        </Typography.Text>
      </Flex>

      <RatingStars value={form.rating} onChange={form.setRating} />

      <Flex align="stretch" direction="column" gapY={4}>
        <Textarea
          className={styles.Feedback}
          mode="secondary"
          rows={3}
          placeholder="Что понравилось или что пошло не так"
          value={form.feedback}
          onChange={(event) => form.setFeedback(event.target.value)}
        />
        <Typography.Text
          className={styles.Counter}
          variant="detail"
          color="secondary"
        >
          {form.feedback.length} / {FEEDBACK_LIMIT}
        </Typography.Text>
      </Flex>

      {(form.repeatError || form.rateError) && (
        <Typography.Text variant="description" className={styles.Failed}>
          {form.repeatError || form.rateError}
        </Typography.Text>
      )}

      <Flex direction="row-reverse" wrap="wrap" gap={8}>
        <Button
          className={styles.Action}
          size="large"
          loading={form.isRating}
          disabled={!form.canRate}
          onClick={form.rate}
        >
          Отправить
        </Button>
        <Button
          className={styles.Action}
          size="large"
          variant="secondary"
          loading={form.isRepeating}
          disabled={!form.canRepeat}
          onClick={form.repeat}
        >
          Проблема вернулась
        </Button>
      </Flex>

      <Typography.Text variant="detail" color="secondary">
        «Проблема вернулась» создаст повторную заявку со ссылкой на эту
      </Typography.Text>
    </div>
  );
};
