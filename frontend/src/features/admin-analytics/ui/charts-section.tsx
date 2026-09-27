import { Flex, Typography } from "@maxhub/max-ui";
import {
  Bar,
  BarChart,
  LabelList,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  type TooltipContentProps,
  XAxis,
  YAxis,
} from "recharts";

import type { components } from "@/shared/api/schema/generated";
import { formatDay } from "@/shared/lib/format";

import { formatMetric } from "../domain/metric";

import styles from "./charts-section.module.css";

type ChartSeries = components["schemas"]["ChartSeries"];

const CategoryChart = ({ series }: { series: ChartSeries }) => {
  const points =
    series.key === "by_category"
      ? series.points.filter((point) => point.value > 0)
      : series.points;

  return (
    <ResponsiveContainer width="100%" height={points.length * 32 + 16}>
      <BarChart
        layout="vertical"
        data={points}
        margin={{ top: 0, right: 32, bottom: 0, left: 0 }}
        barCategoryGap={6}
      >
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="label"
          width={132}
          axisLine={false}
          tickLine={false}
          className={styles.Axis}
        />
        <Bar
          dataKey="value"
          name={series.title}
          fill="var(--button-primary)"
          radius={4}
          isAnimationActive={false}
        >
          <LabelList
            dataKey="value"
            position="right"
            formatter={(value) => formatMetric(Number(value), series.unit)}
            className={styles.BarValue}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
};

const WeekTooltip = ({
  active,
  payload,
  label,
  unit,
}: TooltipContentProps & { unit: ChartSeries["unit"] }) => {
  const point = payload?.[0];

  if (!active || !point) {
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
        Неделя с {formatDay(`${label}T00:00`)} {String(label).slice(0, 4)}
      </Typography.Text>

      <Typography.Text variant="detail" color="secondary">
        {formatMetric(Number(point.value), unit)}
      </Typography.Text>
    </Flex>
  );
};

const WeekChart = ({ series }: { series: ChartSeries }) => (
  <ResponsiveContainer width="100%" height={160}>
    <LineChart
      data={series.points}
      margin={{ top: 8, right: 20, bottom: 0, left: 20 }}
    >
      <XAxis
        dataKey="label"
        interval={2}
        padding={{ left: 8, right: 8 }}
        axisLine={false}
        tickLine={false}
        tickFormatter={(iso: string) => `${iso.slice(8)}.${iso.slice(5, 7)}`}
        className={styles.Axis}
      />
      <YAxis hide domain={["auto", "auto"]} />
      <Tooltip
        cursor={{ stroke: "var(--icon-tertiary)" }}
        content={(props) => <WeekTooltip {...props} unit={series.unit} />}
      />
      <Line
        type="monotone"
        dataKey="value"
        name={series.title}
        stroke="var(--button-primary)"
        strokeWidth={2}
        dot={{ r: 2, fill: "var(--button-primary)" }}
        isAnimationActive={false}
      />
    </LineChart>
  </ResponsiveContainer>
);

export const ChartsSection = ({ charts }: { charts: ChartSeries[] }) => (
  <Flex direction="column" align="stretch" gapY={12}>
    {charts.map((series) => (
      <Flex
        key={series.key}
        className={styles.Card}
        direction="column"
        align="stretch"
        gapY={8}
      >
        <Typography.Text variant="body-strong" color="primary">
          {series.title}
        </Typography.Text>

        <div className={styles.Chart}>
          {series.key === "by_week" ? (
            <WeekChart series={series} />
          ) : (
            <CategoryChart series={series} />
          )}
        </div>

        {series.key === "by_week" && (
          <Typography.Text variant="detail" color="tertiary">
            последние 12 недель
          </Typography.Text>
        )}
      </Flex>
    ))}
  </Flex>
);
