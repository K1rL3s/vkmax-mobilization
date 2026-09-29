import {
  Button,
  Flex,
  IconButton,
  Input,
  Panel,
  Textarea,
  Typography,
} from "@maxhub/max-ui";
import { Controller } from "react-hook-form";

import { DateInput } from "@/shared/ui/date-input";
import { Icon, pollIcon, trashIcon } from "@/shared/ui/icon";
import { EmptyState } from "@/shared/ui/state";

import { pollFormConstraints } from "./domain/poll-draft";
import { useNewPoll } from "./model/use-new-poll";
import { DescriptionCounter } from "./ui/description-counter";

import styles from "./new-poll.module.css";

const NewPollPage = () => {
  const form = useNewPoll();

  if (!form.isChairman) {
    return (
      <EmptyState
        fill
        icon={pollIcon}
        title="Опрос заводит председатель"
        description="Создать опрос дома может председатель совета дома или управляющая компания."
      />
    );
  }

  return (
    <Panel className={styles.Page} mode="secondary">
      <div className={styles.Content}>
        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>О чём опрос</h2>
            </Typography.Text>

            <Input
              placeholder="Например: установка шлагбаума во дворе"
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
          </section>
        </Flex>

        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>Варианты ответа</h2>
            </Typography.Text>

            {form.options.map((option, index) => (
              <div key={option.id} className={styles.OptionRow}>
                <Input
                  placeholder={`Вариант ${index + 1}`}
                  maxLength={pollFormConstraints.option}
                  hint={form.errors.options?.[index]?.text?.message}
                  innerClassNames={{ hint: styles.Error }}
                  {...form.registerOption(index)}
                />

                {form.canRemoveOption && (
                  <IconButton
                    variant="secondary"
                    size="small"
                    aria-label={`Убрать вариант ${index + 1}`}
                    onClick={() => form.removeOption(index)}
                  >
                    <Icon src={trashIcon} size={20} />
                  </IconButton>
                )}
              </div>
            ))}

            <Button
              size="medium"
              variant="secondary"
              disabled={!form.canAddOption}
              onClick={form.addOption}
            >
              Добавить вариант
            </Button>

            <Typography.Text
              className={form.optionsError && styles.Error}
              variant="description"
              color={form.optionsError ? undefined : "secondary"}
            >
              {form.optionsError ?? "Житель выбирает один вариант."}
            </Typography.Text>
          </section>
        </Flex>

        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>До какого дня</h2>
            </Typography.Text>

            <Controller
              control={form.control}
              name="endsAt"
              render={({ field }) => (
                <DateInput
                  hint={form.errors.endsAt?.message}
                  innerClassNames={{ hint: styles.Error }}
                  name={field.name}
                  value={field.value}
                  onChange={field.onChange}
                  onBlur={field.onBlur}
                />
              )}
            />

            <Typography.Text variant="description" color="secondary">
              Голосование закроется в конце выбранного дня.
            </Typography.Text>
          </section>
        </Flex>

        {form.isFailed && (
          <Typography.Text className={styles.Error} variant="description">
            Опрос не создался. Проверьте связь и попробуйте ещё раз.
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
          Создать опрос
        </Button>
      </div>
    </Panel>
  );
};

export const Component = NewPollPage;
