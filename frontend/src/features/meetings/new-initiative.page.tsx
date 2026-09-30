import {
  Button,
  Flex,
  Input,
  Panel,
  Textarea,
  Typography,
} from "@maxhub/max-ui";

import { errorMessage } from "@/shared/api/errors";
import { pollIcon } from "@/shared/ui/icon";
import { EmptyState } from "@/shared/ui/state";

import { pollFormConstraints } from "./domain/poll-draft";
import { useNewInitiative } from "./model/use-new-initiative";
import { DescriptionCounter } from "./ui/description-counter";

import styles from "./new-initiative.module.css";

const NewInitiativePage = () => {
  const form = useNewInitiative();

  if (!form.canPropose) {
    return (
      <EmptyState
        fill
        icon={pollIcon}
        title="Инициативу предлагает собственник"
        description="Предложить инициативу дома может собственник подтверждённой квартиры в подключённом доме."
      />
    );
  }

  return (
    <Panel className={styles.Page} mode="secondary">
      <div className={styles.Content}>
        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>Что предлагаете</h2>
            </Typography.Text>

            <Input
              placeholder="Например: велопарковка у второго подъезда"
              maxLength={pollFormConstraints.title}
              hint={form.errors.title?.message}
              innerClassNames={{ hint: styles.Error }}
              {...form.register("title")}
            />

            <Textarea
              rows={3}
              mode="secondary"
              placeholder="Объясните соседям, о чём речь. Необязательно"
              maxLength={pollFormConstraints.description}
              {...form.register("description")}
            />

            <DescriptionCounter
              control={form.control}
              className={styles.Counter}
            />

            <Typography.Text variant="description" color="secondary">
              Соседи ответят «Поддерживаю» или «Против», сбор идёт 14 дней.
              Закрыть его досрочно может председатель совета дома.
            </Typography.Text>
          </section>
        </Flex>

        {form.error !== null && (
          <Typography.Text className={styles.Error} variant="description">
            {errorMessage(
              form.error,
              "Инициатива не создалась. Проверьте связь и попробуйте ещё раз",
            )}
          </Typography.Text>
        )}
      </div>

      <div className={styles.Footer}>
        <Button
          size="large"
          stretched
          loading={form.isSubmitting}
          disabled={form.isSubmitting}
          onClick={form.submit}
        >
          Предложить инициативу
        </Button>
      </div>
    </Panel>
  );
};

export const Component = NewInitiativePage;
