import { Flex, Typography } from "@maxhub/max-ui";

import { useRequestCategories } from "@/features/request";
import { errorMessage } from "@/shared/api/errors";
import { orgParams } from "@/shared/model/session";
import { ErrorState, LoadingState } from "@/shared/ui/state";

import {
  useCategoryExecutors,
  useOrgExecutors,
  useSetCategoryExecutor,
} from "../model/use-org";

import styles from "./category-executors.module.css";

export const CategoryExecutors = ({ readOnly }: { readOnly: boolean }) => {
  const categories = useRequestCategories();
  const executors = useOrgExecutors();
  const chosen = useCategoryExecutors();
  const save = useSetCategoryExecutor();
  const queries = [categories, executors, chosen];

  const body = () => {
    if (queries.some((query) => query.isPending))
      return <LoadingState title="Загружаем исполнителей" />;
    if (!categories.data || !executors.data || !chosen.data)
      return (
        <ErrorState
          error={categories.error ?? executors.error ?? chosen.error}
          onRetry={() => queries.forEach((query) => void query.refetch())}
        />
      );

    const byCategory = new Map(
      chosen.data.map((item) => [item.category, item.executor_user_id]),
    );

    return categories.data.map((item) => (
      <label key={item.category} className={styles.Row}>
        <Typography.Text variant="description" color="secondary">
          {item.label}
        </Typography.Text>
        <select
          className={styles.Select}
          value={byCategory.get(item.category) ?? ""}
          disabled={readOnly || save.isPending}
          onChange={(event) =>
            save.mutate({
              params: orgParams(),
              body: {
                category: item.category,
                executor_user_id: event.target.value
                  ? Number(event.target.value)
                  : null,
              },
            })
          }
        >
          <option value="">Не назначен</option>
          {executors.data.map((executor) => (
            <option key={executor.user_id} value={executor.user_id}>
              {executor.name}
            </option>
          ))}
        </select>
      </label>
    ));
  };

  return (
    <Flex asChild align="stretch" direction="column" gapY={8}>
      <section className={styles.Section}>
        <Typography.Text asChild variant="title" color="primary">
          <h2>Исполнители по категориям</h2>
        </Typography.Text>
        <div className={styles.Card}>{body()}</div>
        {save.isError && (
          <Typography.Text className={styles.Error} variant="description">
            {errorMessage(
              save.error,
              "Не получилось сохранить. Проверьте связь и попробуйте ещё раз",
            )}
          </Typography.Text>
        )}
        <Typography.Text variant="description" color="secondary">
          {readOnly
            ? "Исполнителей по категориям назначают создатель и администраторы организации"
            : "Новая заявка категории сразу уходит выбранному исполнителю в MAX. Если он откажется, заявку переназначает диспетчер"}
        </Typography.Text>
      </section>
    </Flex>
  );
};
