import { useState } from "react";
import { Button, Flex, Typography } from "@maxhub/max-ui";
import {
  Line,
  LineChart,
  Tooltip,
  type TooltipContentProps,
  XAxis,
  YAxis,
} from "recharts";

import { ChartBox } from "@/shared/ui/chart-box";

import {
  formatMonth,
  formatVolume,
  SERVICE_LABEL,
  SERVICE_UNIT,
  type ServiceConsumption,
} from "./charge";

import styles from "./consumption-chart.module.css";

export const ConsumptionChart = ({
  series,
}: {
  series: ServiceConsumption[];
}) => {
  const [selected, setSelected] = useState(0);
  const current = series[selected] ?? series[0];

  if (!current) {
    return null;
  }

  const unit = SERVICE_UNIT[current.service] ?? "";
  const average = current.house_average ?? null;
  const data = current.points.map((point) => ({
    month: formatMonth(point.period),
    own: point.consumption / 1000,
    house: average === null ? null : average / 1000,
  }));

  return (
    <Flex direction="column" align="stretch" gap={12}>
      {series.length > 1 && (
        <div className={styles.Chips}>
          {series.map((item, index) => (
            <Button
              key={item.service}
              size="small"
              variant={index === selected ? "primary" : "secondary"}
              aria-pressed={index === selected}
              onClick={() => setSelected(index)}
            >
              {SERVICE_LABEL[item.service]}
            </Button>
          ))}
        </div>
      )}

      <div className={styles.Card}>
        {data.length < 2 ? (
          <Typography.Text variant="description" color="secondary">
            Для графика нужно хотя бы два месяца показаний
          </Typography.Text>
        ) : (
          <ChartBox height={140}>
            <LineChart
              data={data}
              margin={{ top: 8, right: 8, bottom: 0, left: 8 }}
            >
              <XAxis
                dataKey="month"
                axisLine={false}
                tickLine={false}
                interval={0}
                padding={{ left: 12, right: 12 }}
                tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
              />
              <YAxis hide domain={["auto", "auto"]} />
              <Tooltip
                cursor={{ stroke: "var(--icon-tertiary)" }}
                content={(props) => <MonthTooltip {...props} unit={unit} />}
              />
              <Line
                type="monotone"
                dataKey="house"
                name="Среднее по дому"
                stroke="var(--icon-tertiary)"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="own"
                name="Ваш расход"
                stroke="var(--button-primary)"
                strokeWidth={2}
                dot={{
                  r: 3,
                  fill: "var(--button-primary)",
                  stroke: "var(--button-primary)",
                }}
                isAnimationActive={false}
              />
            </LineChart>
          </ChartBox>
        )}

        <Flex gap={16} wrap="wrap" className={styles.Legend}>
          <Flex align="center" gap={6}>
            <span className={styles.OwnMark} />
            <Typography.Text variant="description" color="secondary">
              Ваш расход
            </Typography.Text>
          </Flex>
          <Flex align="center" gap={6}>
            <span className={styles.HouseMark} />
            <Typography.Text variant="description" color="secondary">
              {average === null
                ? "Среднего по дому пока нет"
                : `Среднее по дому: ${formatVolume(average)} ${unit}`}
            </Typography.Text>
          </Flex>
        </Flex>
      </div>
    </Flex>
  );
};

const MonthTooltip = ({
  active,
  payload,
  label,
  unit,
}: TooltipContentProps & { unit: string }) => {
  const own = payload?.find((entry) => entry.dataKey === "own");

  if (!active || !own) {
    return null;
  }

  return (
    <Flex
      className={styles.Tooltip}
      direction="column"
      align="stretch"
      gapY={2}
    >
      <Typography.Text variant="detail-strong" color="primary">
        {label}
      </Typography.Text>

      <Typography.Text variant="detail" color="secondary">
        Ваш расход: {formatVolume(Number(own.value) * 1000)} {unit}
      </Typography.Text>
    </Flex>
  );
};
