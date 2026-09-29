import { Button, Flex, Typography } from "@maxhub/max-ui";
import { Link } from "react-router-dom";

import { plural } from "@/shared/lib/format";
import { Routes } from "@/shared/model/routes";
import { alertIcon, checkIcon } from "@/shared/ui/icon";
import { IconTile } from "@/shared/ui/icon-tile";

import {
  formatAmount,
  formatPeriod,
  formatReading,
  METER_LABEL,
  METER_UNIT,
  ZONE_LABEL,
  zonesOf,
  type Meter,
  type ReadingResult,
} from "../domain/reading";

import styles from "./submit-result.module.css";

type SubmitResultProps = {
  result: ReadingResult;
  meter: Meter;
  onResubmit: () => void;
  onNext: (() => void) | undefined;
  onDone: () => void;
};

export const SubmitResult = ({
  result,
  meter,
  onResubmit,
  onNext,
  onDone,
}: SubmitResultProps) => {
  const { reading, house_average: houseAverage } = result;
  const isBelow = reading.is_below_previous || Boolean(result.warning);
  const unit = METER_UNIT[meter.type];
  const zones = zonesOf(meter);
  const total = zones.reduce(
    (sum, zone) => sum + (reading.consumption[zone] ?? 0),
    0,
  );
  const scale = Math.max(total, houseAverage ?? 0) || 1;
  const difference = houseAverage
    ? Math.round(((total - houseAverage) / houseAverage) * 100)
    : null;
  const times = houseAverage ? Math.round(total / houseAverage) : 0;

  return (
    <>
      <div className={styles.Content}>
        <Flex
          direction="column"
          align="center"
          gap={16}
          className={styles.Hero}
        >
          <IconTile
            icon={isBelow ? alertIcon : checkIcon}
            tone={isBelow ? "negative" : "positive"}
            size="xlarge"
          />
          <Flex direction="column" align="center" gapY={4}>
            <Typography.Text asChild variant="header" color="primary">
              <h1 className={styles.Title}>
                {isBelow ? "Проверьте показания" : "Показания отправлены"}
              </h1>
            </Typography.Text>
            <Typography.Text variant="body" color="secondary">
              {METER_LABEL[meter.type]} · {formatPeriod(reading.period)}
            </Typography.Text>
          </Flex>
        </Flex>

        {isBelow && (
          <Flex
            direction="column"
            align="stretch"
            gap={8}
            className={styles.Warning}
          >
            <Typography.Text variant="body-strong" color="primary">
              {result.warning ?? "Новое значение меньше предыдущего"}
            </Typography.Text>
            <Typography.Text variant="description" color="secondary">
              Показания приняты, но расход и сумму не считаем: с такими цифрами
              они будут неверными. Если ошиблись, переподайте показания
            </Typography.Text>
          </Flex>
        )}

        {!isBelow && (
          <Flex asChild direction="column" align="stretch" gap={8}>
            <section>
              <Typography.Text asChild variant="title" color="primary">
                <h2>Расход за месяц</h2>
              </Typography.Text>

              <div className={styles.Panel}>
                {zones.map((zone) => {
                  const value = reading.values[zone] ?? 0;
                  const spent = reading.consumption[zone] ?? 0;

                  return (
                    <Flex
                      key={zone}
                      align="center"
                      gap={12}
                      className={styles.Line}
                    >
                      <Flex
                        direction="column"
                        align="stretch"
                        gapY={2}
                        className={styles.Grow}
                      >
                        <Typography.Text variant="detail" color="primary">
                          {zone === "single" ? "За месяц" : ZONE_LABEL[zone]}
                        </Typography.Text>
                        <Typography.Text
                          variant="description"
                          color="secondary"
                        >
                          {spent === 0
                            ? "Первое показание, расход пойдёт со следующего"
                            : `${formatReading(value - spent)} → ${formatReading(value)}`}
                        </Typography.Text>
                      </Flex>
                      <Typography.Text variant="detail-strong" color="primary">
                        {formatReading(spent)} {unit}
                      </Typography.Text>
                    </Flex>
                  );
                })}

                {reading.amount != null && (
                  <Flex
                    direction="column"
                    align="stretch"
                    gapY={2}
                    className={styles.Line}
                  >
                    <Flex align="center" gap={12}>
                      <Typography.Text
                        variant="detail-strong"
                        color="primary"
                        className={styles.Grow}
                      >
                        К оплате
                      </Typography.Text>
                      <Typography.Text variant="subheader" color="primary">
                        ≈ {formatAmount(reading.amount)}
                      </Typography.Text>
                    </Flex>
                    <Typography.Text variant="description" color="tertiary">
                      Предварительный расчёт, итог в квитанции
                    </Typography.Text>
                  </Flex>
                )}
              </div>
            </section>
          </Flex>
        )}

        {!isBelow && houseAverage != null && (
          <Flex asChild direction="column" align="stretch" gap={8}>
            <section>
              <Typography.Text asChild variant="title" color="primary">
                <h2>Сравнение с домом</h2>
              </Typography.Text>

              <Flex
                direction="column"
                align="stretch"
                gap={12}
                className={styles.Comparison}
              >
                <Bar
                  label="Ваша квартира"
                  value={total}
                  unit={unit}
                  scale={scale}
                  fill={styles.Fill}
                />
                <Bar
                  label="Среднее по дому"
                  value={houseAverage}
                  unit={unit}
                  scale={scale}
                  fill={styles.HouseFill}
                />

                {difference !== null && (
                  <Typography.Text variant="description" color="secondary">
                    {comparison(difference, times)}
                  </Typography.Text>
                )}
              </Flex>
            </section>
          </Flex>
        )}

        {result.suggested_category && (
          <Flex
            direction="column"
            align="stretch"
            gap={8}
            className={styles.Suggest}
          >
            <Typography.Text variant="description" color="primary">
              Расход заметно выше обычного. Если так быть не должно, расскажите
              об этом УК
            </Typography.Text>
            <Button asChild size="medium" variant="secondary">
              <Link to={Routes.REQUEST_NEW}>Подать заявку</Link>
            </Button>
          </Flex>
        )}

        <Flex direction="column" align="stretch" gap={8}>
          {onNext && (
            <Button
              size="large"
              variant={isBelow ? "secondary" : "primary"}
              stretched
              onClick={onNext}
            >
              Следующий счётчик
            </Button>
          )}
          <Button
            size="large"
            variant={isBelow ? "primary" : "secondary"}
            stretched
            onClick={onResubmit}
          >
            Изменить показания
          </Button>
          <Typography.Text
            variant="description"
            color="tertiary"
            className={styles.Note}
          >
            Переподать можно, пока открыто окно
          </Typography.Text>
        </Flex>
      </div>

      <div className={styles.Footer}>
        <Button
          size="large"
          stretched
          variant={onNext ? "secondary" : "primary"}
          onClick={onDone}
        >
          Готово
        </Button>
      </div>
    </>
  );
};

type BarProps = {
  label: string;
  value: number;
  unit: string;
  scale: number;
  fill: string | undefined;
};

const Bar = ({ label, value, unit, scale, fill }: BarProps) => (
  <Flex direction="column" align="stretch" gap={8}>
    <Flex align="center" gap={8}>
      <Typography.Text variant="detail" color="primary" className={styles.Grow}>
        {label}
      </Typography.Text>
      <Typography.Text variant="detail-strong" color="primary">
        {formatReading(value)} {unit}
      </Typography.Text>
    </Flex>
    <div className={styles.Track}>
      <div className={fill} style={{ width: `${(value / scale) * 100}%` }} />
    </div>
  </Flex>
);

const comparison = (difference: number, times: number): string => {
  if (difference === 0) {
    return "Столько же, сколько в среднем по дому";
  }

  if (times >= 2) {
    return `В ${times} ${plural(times, ["раз", "раза", "раз"])} больше среднего по дому`;
  }

  return `На ${Math.abs(difference)}% ${difference < 0 ? "меньше" : "больше"} среднего по дому`;
};
