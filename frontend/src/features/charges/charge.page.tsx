import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { errorMessage } from "@/shared/api/errors";
import { cn } from "@/shared/lib/css";
import { formatDay } from "@/shared/lib/format";
import { useRouteParams } from "@/shared/lib/router";
import { Routes } from "@/shared/model/routes";
import { checkIcon, receiptIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import {
  formatMoney,
  formatPeriod,
  formatTariff,
  formatVolume,
  toMonthDative,
  type ChargeBreakdown,
  type ChargeCard,
} from "./charge";
import { ModelNote } from "./charges-section";
import { ConsumptionChart } from "./consumption-chart";
import { useCharge } from "./use-charges";

import styles from "./charge.module.css";

const paramsSchema = z.object({ chargeId: z.coerce.number().int().positive() });

const signed = (kopecks: number) => formatMoney(kopecks, true);

const Amount = ({ value }: { value: string }) => (
  <Typography.Text variant="body-strong" color="primary">
    {value}
  </Typography.Text>
);

const Row = ({ title, value }: { title: string; value: string }) => (
  <Flex align="center" gap={12} className={styles.Line}>
    <Typography.Text variant="body" color="primary" className={styles.Grow}>
      {title}
    </Typography.Text>
    <Amount value={value} />
  </Flex>
);

const DeltaSummary = ({ breakdown }: { breakdown: ChargeBreakdown }) => {
  if (!breakdown.previous_period) {
    return (
      <Typography.Text variant="description" color="secondary">
        Первый месяц в истории квартиры - сравнить пока не с чем
      </Typography.Text>
    );
  }

  const changed = breakdown.lines.filter(
    (line) => !line.appeared && !line.disappeared,
  );
  const tariff = changed.reduce((sum, line) => sum + line.tariff_effect, 0);
  const volume = changed.reduce((sum, line) => sum + line.volume_effect, 0);
  const rest = breakdown.lines
    .filter((line) => line.appeared || line.disappeared)
    .reduce((sum, line) => sum + line.delta, 0);

  return (
    <div className={styles.Panel}>
      <Flex direction="column" align="stretch" gap={2} className={styles.Line}>
        <Typography.Text variant="subheader" color="primary">
          {signed(breakdown.delta)}
        </Typography.Text>
        <Typography.Text variant="description" color="secondary">
          к {toMonthDative(breakdown.previous_period)}
          {breakdown.previous_total != null &&
            `: было ${formatMoney(breakdown.previous_total)}`}
        </Typography.Text>
      </Flex>
      <Row title="Изменился тариф" value={signed(tariff)} />
      <Row title="Изменился расход" value={signed(volume)} />
      {rest !== 0 && (
        <Row title="Новые и ушедшие строки" value={signed(rest)} />
      )}
    </div>
  );
};

const Lines = ({
  breakdown,
  card,
}: {
  breakdown: ChargeBreakdown;
  card: ChargeCard;
}) => (
  <div className={styles.Panel}>
    {breakdown.lines.map((line) => {
      const source = card.lines.find((item) => item.service === line.service);
      const calculation =
        source?.volume != null && source.tariff != null
          ? `${formatVolume(source.volume)} ${source.unit ?? ""} × ${formatTariff(source.tariff)}`
          : null;

      const change = () => {
        if (!breakdown.previous_period) {
          return null;
        }

        if (line.appeared) {
          return "новая строка в этом месяце";
        }

        if (line.disappeared) {
          return `строки больше нет, было ${formatMoney(line.previous_amount ?? 0)}`;
        }

        return line.delta === 0
          ? "без изменений"
          : `${signed(line.delta)}: тариф ${signed(line.tariff_effect)}, расход ${signed(line.volume_effect)}`;
      };

      return (
        <Flex
          key={line.service}
          direction="column"
          align="stretch"
          gap={2}
          className={styles.Line}
        >
          <Flex align="center" gap={12}>
            <Typography.Text
              variant="body"
              color="primary"
              className={styles.Grow}
            >
              {line.label}
            </Typography.Text>
            <Amount value={formatMoney(line.amount)} />
          </Flex>
          {calculation && (
            <Typography.Text variant="description" color="secondary">
              {calculation}
            </Typography.Text>
          )}
          {change() && (
            <Typography.Text
              variant="description"
              color={line.delta > 0 ? "primary" : "secondary"}
            >
              {change()}
            </Typography.Text>
          )}
        </Flex>
      );
    })}
  </div>
);

const ChargePage = () => {
  const navigate = useNavigate();
  const params = useRouteParams(paramsSchema);
  const { card, breakdown, pay, submitPay } = useCharge(params?.chargeId ?? 0);

  if (!params) {
    return (
      <EmptyState
        fill
        icon={receiptIcon}
        title="Квитанция не найдена"
        description="Похоже, ссылка устарела. Откройте месяц из истории начислений"
      />
    );
  }

  if (card.isPending || breakdown.isPending) {
    return <LoadingState fill title="Загружаем квитанцию" />;
  }

  if (card.isError || breakdown.isError) {
    return (
      <ErrorState
        fill
        error={card.error ?? breakdown.error}
        onRetry={() => {
          void card.refetch();
          void breakdown.refetch();
        }}
      />
    );
  }

  const charge = card.data;
  const period = formatPeriod(charge.period);

  const status = () => {
    if (charge.paid_at) {
      return `Оплачено ${formatDay(charge.paid_at)} · демо`;
    }

    return charge.is_closed ? "Не оплачено" : "Месяц ещё не закрыт";
  };

  return (
    <Panel className={styles.Page} mode="secondary">
      <Flex align="center" gap={12} className={styles.Summary}>
        <IconTile
          icon={charge.paid_at ? checkIcon : receiptIcon}
          tone={charge.paid_at ? "positive" : "themed"}
          size="large"
        />
        <Flex
          direction="column"
          align="stretch"
          gapY={2}
          className={styles.Grow}
        >
          <Typography.Text asChild variant="title" color="primary">
            <h1>
              {period} · {formatMoney(charge.total)}
            </h1>
          </Typography.Text>
          <Typography.Text variant="description" color="secondary">
            {charge.address} · кв. {charge.flat_number}
          </Typography.Text>
          <Typography.Text variant="description" color="secondary">
            {status()}
          </Typography.Text>
        </Flex>
      </Flex>

      <Flex asChild align="stretch" direction="column" gap={8}>
        <section>
          <Typography.Text asChild variant="title" color="primary">
            <h2>Что изменилось</h2>
          </Typography.Text>
          <DeltaSummary breakdown={breakdown.data} />
        </section>
      </Flex>

      <Flex asChild align="stretch" direction="column" gap={8}>
        <section>
          <Typography.Text asChild variant="title" color="primary">
            <h2>Построчно</h2>
          </Typography.Text>
          {breakdown.data.lines.length === 0 ? (
            <Typography.Text variant="description" color="secondary">
              В квитанции нет строк: УК выставила пустой месяц
            </Typography.Text>
          ) : (
            <Lines breakdown={breakdown.data} card={charge} />
          )}
        </section>
      </Flex>

      {breakdown.data.consumption && breakdown.data.consumption.length > 0 && (
        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>Расход за полгода</h2>
            </Typography.Text>
            <ConsumptionChart series={breakdown.data.consumption} />
          </section>
        </Flex>
      )}

      <Flex direction="column" align="stretch" gap={8}>
        {charge.paid_at ? (
          <Flex align="center" gap={12} className={styles.Paid}>
            <IconTile icon={checkIcon} tone="positive" />
            <Flex direction="column" gapY={2} className={styles.Grow}>
              <Typography.Text variant="body-strong" color="primary">
                {period} отмечен оплаченным
              </Typography.Text>
              <Typography.Text variant="description" color="secondary">
                Демо-оплата: платёж не проводился, деньги не списаны
              </Typography.Text>
            </Flex>
          </Flex>
        ) : (
          <>
            <Button
              size="large"
              stretched
              loading={pay.isPending}
              onClick={submitPay}
            >
              Оплатить {formatMoney(charge.total)} · демо
            </Button>
            <Typography.Text
              variant="description"
              color="secondary"
              className={cn(styles.Center, pay.isError && styles.Failed)}
            >
              {pay.isError
                ? errorMessage(
                    pay.error,
                    "Оплата не прошла. Попробуйте ещё раз",
                  )
                : "Модельные данные: деньги не списываются, месяц только отмечается оплаченным"}
            </Typography.Text>
          </>
        )}

        <Button
          size="large"
          variant="secondary"
          stretched
          onClick={() =>
            void navigate(Routes.REQUEST_NEW, {
              state: { category: "charge_dispute", chargeId: charge.id },
            })
          }
        >
          Оспорить начисление
        </Button>
      </Flex>

      <ModelNote text="Начисления и оплата - модельные данные для демонстрации" />
    </Panel>
  );
};

export const Component = ChargePage;
