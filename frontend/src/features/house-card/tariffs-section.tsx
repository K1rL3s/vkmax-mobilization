import { CellSimple, Flex, Typography } from "@maxhub/max-ui";

import type { components } from "@/shared/api/schema/generated";
import { authParams, rqClient } from "@/shared/api/instance";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";
import { receiptIcon } from "@/shared/ui/icon";

import styles from "./house-card.module.css";

type Tariff = components["schemas"]["TariffItem"];

const dateFormat = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
  year: "numeric",
});

const since = (date: string) =>
  `с ${dateFormat.format(new Date(`${date}T00:00`)).replace(" г.", "")}`;

const price = (tariff: Tariff) =>
  `${(tariff.value / 10000).toLocaleString("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  })} ₽/${tariff.unit}`;

const currentTariffs = (tariffs: Tariff[]) => {
  const today = new Date().toLocaleDateString("sv-SE");
  const seen = new Set<string>();

  return tariffs
    .filter((tariff) => tariff.valid_from <= today)
    .sort((a, b) => b.valid_from.localeCompare(a.valid_from))
    .filter((tariff) => {
      if (seen.has(tariff.service)) {
        return false;
      }

      seen.add(tariff.service);

      return true;
    });
};

export const TariffsSection = ({
  houseId,
  isConnected,
}: {
  houseId: number;
  isConnected: boolean;
}) => {
  const query = rqClient.useQuery("get", "/api/houses/{house_id}/tariffs", {
    params: { ...authParams(), path: { house_id: houseId } },
  });

  const tariffs = query.data ? currentTariffs(query.data) : [];
  const dates = new Set(tariffs.map((tariff) => tariff.valid_from));
  const shared = dates.size === 1 ? tariffs[0].valid_from : null;

  const content = () => {
    if (query.isPending) {
      return <LoadingState title="Загружаем тарифы" />;
    }

    if (query.isError) {
      return (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      );
    }

    if (tariffs.length === 0) {
      return (
        <EmptyState
          icon={receiptIcon}
          title="Тарифов пока нет"
          description={
            isConnected
              ? "УК ещё не опубликовала тарифы дома. Они появятся здесь, как только она их внесёт"
              : "Тарифы публикует УК из своего кабинета. Они появятся, когда дом подключат к сервису"
          }
        />
      );
    }

    return (
      <div className={styles.Panel}>
        {tariffs.map((tariff, index) => {
          const row = {
            separator: index > 0,
            title: tariff.label,
            subtitle: shared ? undefined : since(tariff.valid_from),
            after: (
              <Typography.Text
                variant="body-strong"
                color="primary"
                className={styles.Price}
              >
                {price(tariff)}
              </Typography.Text>
            ),
          };

          return tariff.document ? (
            <CellSimple key={tariff.id} {...row} showChevron asChild>
              <a href={tariff.document.url} target="_blank" rel="noreferrer" />
            </CellSimple>
          ) : (
            <CellSimple key={tariff.id} {...row} />
          );
        })}
      </div>
    );
  };

  return (
    <Flex asChild align="stretch" direction="column" gap={8}>
      <section>
        <Flex align="baseline" justify="space-between" gap={8} wrap="wrap">
          <Typography.Text asChild variant="title" color="primary">
            <h2>Тарифы ЖКУ</h2>
          </Typography.Text>
          {shared && (
            <Typography.Text variant="description" color="tertiary">
              {since(shared)}
            </Typography.Text>
          )}
        </Flex>
        {content()}
      </section>
    </Flex>
  );
};
