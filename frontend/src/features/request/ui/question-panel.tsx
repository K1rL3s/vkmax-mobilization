import { Typography } from "@maxhub/max-ui";

import type { RequestCard } from "../domain/types";

import { ReplyForm } from "./reply-form";

import styles from "./question-panel.module.css";

export const QuestionPanel = ({ request }: { request: RequestCard }) => {
  const question = request.messages.findLast(
    (message) => message.author_role === "staff",
  );

  return (
    <section className={styles.Panel}>
      <Typography.Text asChild variant="title" color="primary">
        <h2>УК ждёт вашего ответа</h2>
      </Typography.Text>
      {question && (
        <Typography.Text className={styles.Text} variant="body" color="primary">
          {question.text}
        </Typography.Text>
      )}
      <ReplyForm requestId={request.id} />
    </section>
  );
};
