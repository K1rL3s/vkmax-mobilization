import { useState } from "react";
import { Button, CellSimple, Flex, Radio, Typography } from "@maxhub/max-ui";

import { type RequestCategory, useRequestCategories } from "@/features/request";
import { errorMessage } from "@/shared/api/errors";
import { orgParams } from "@/shared/model/session";
import { BottomSheet } from "@/shared/ui/bottom-sheet";
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
  const [picking, setPicking] = useState<{
    category: RequestCategory;
    label: string;
  } | null>(null);
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

    const options = [
      { id: null, name: "Не назначен" },
      ...executors.data.map((executor) => ({
        id: executor.user_id,
        name: executor.name,
      })),
    ];
    const nameOf = (id: number | null | undefined) =>
      options.find((option) => option.id === (id ?? null))?.name ??
      "Не назначен";

    return (
      <>
        {categories.data.map((item, index) => (
          <CellSimple
            key={item.category}
            separator={index > 0}
            overline={item.label}
            title={nameOf(byCategory.get(item.category))}
            showChevron={!readOnly}
            onClick={
              readOnly
                ? undefined
                : () =>
                    setPicking({ category: item.category, label: item.label })
            }
          />
        ))}

        <BottomSheet isOpen={picking !== null} onClose={() => setPicking(null)}>
          {picking && (
            <Flex direction="column" align="stretch" gapY={12}>
              <Flex direction="column" gapY={4}>
                <Typography.Text asChild variant="title" color="primary">
                  <h2 className={styles.SheetTitle}>{picking.label}</h2>
                </Typography.Text>
                <Typography.Text variant="description" color="secondary">
                  Кому сразу уходят новые заявки этой категории
                </Typography.Text>
              </Flex>

              <div className={styles.Options}>
                {options.map((option, index) => (
                  <CellSimple
                    key={option.id ?? "none"}
                    as="label"
                    separator={index > 0}
                    title={option.name}
                    after={
                      <Radio
                        name="category-executor"
                        checked={
                          (byCategory.get(picking.category) ?? null) ===
                          option.id
                        }
                        onChange={() => {
                          save.mutate({
                            params: orgParams(),
                            body: {
                              category: picking.category,
                              executor_user_id: option.id,
                            },
                          });
                          setPicking(null);
                        }}
                      />
                    }
                  />
                ))}
              </div>

              <Button
                size="large"
                variant="secondary"
                stretched
                onClick={() => setPicking(null)}
              >
                Отмена
              </Button>
            </Flex>
          )}
        </BottomSheet>
      </>
    );
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
