import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import { generatePath, Link, useNavigate } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { meterIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { formatPeriod, METER_UNIT } from "./domain/reading";
import { useReadingForm } from "./model/use-reading-form";
import { PHOTO_LIMIT, useReadingPhotos } from "./model/use-reading-photos";
import { MeterChips } from "./ui/meter-chips";
import { PeriodCard } from "./ui/period-card";
import { PhotoStrip } from "./ui/photo-strip";
import { ReadingFields } from "./ui/reading-fields";
import { SubmitResult } from "./ui/submit-result";

import styles from "./meters.module.css";

const photoHint = (photos: ReturnType<typeof useReadingPhotos>) => {
  if (photos.isFailed) {
    return "Фото не загрузилось, попробуйте ещё раз";
  }

  if (photos.isRecognizing) {
    return "Распознаём показания с фото";
  }

  if (photos.isUnrecognized) {
    return "Не удалось распознать, введите показание вручную";
  }

  if (photos.recognized) {
    return "Значения с фото подставили в поля ниже - проверьте их";
  }

  return `Снимите табло целиком, до ${PHOTO_LIMIT} фото`;
};

const MetersPage = () => {
  const navigate = useNavigate();
  const form = useReadingForm();
  const residency = form.residency;

  if (residency && !residency.verified) {
    return (
      <EmptyState
        fill
        icon={meterIcon}
        title="Сначала подтвердите квартиру"
        description="Показания принимаются только от подтверждённого жителя - это занимает пару минут"
        action={
          <Button asChild size="medium">
            <Link
              to={generatePath(Routes.FLAT_CONFIRMATION, {
                residentId: String(residency.resident_id),
              })}
            >
              Подтвердить квартиру
            </Link>
          </Button>
        }
      />
    );
  }

  if (form.isPending) {
    return <LoadingState fill title="Загружаем счётчики" />;
  }

  if (form.isError) {
    return <ErrorState error={form.loadError} fill onRetry={form.refetch} />;
  }

  const meter = form.meter;

  if (!meter) {
    return (
      <EmptyState
        fill
        icon={meterIcon}
        title="Счётчиков пока нет"
        description="Приборы учёта квартиры заводит управляющая компания. Напишите в УК, если счётчик у вас стоит"
      />
    );
  }

  if (form.result) {
    return (
      <Panel className={styles.Page} mode="secondary">
        <SubmitResult
          result={form.result}
          meter={meter}
          onResubmit={form.resubmit}
          onNext={form.openNext}
          onDone={() => void navigate(Routes.HOME)}
        />
      </Panel>
    );
  }

  if (!form.period) {
    return (
      <EmptyState
        fill
        icon={meterIcon}
        title="Окно подачи закрыто"
        description="Показания принимаются не весь месяц. Загляните позже - окно откроет управляющая компания"
      />
    );
  }

  return (
    <Panel className={styles.Page} mode="secondary">
      <div className={styles.Content}>
        <PeriodCard
          period={form.period}
          flatNumber={residency?.flat_number ?? null}
          submitted={meter.last_period === form.period.period}
        />

        <Flex asChild align="stretch" direction="column" gap={12}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>Какой счётчик?</h2>
            </Typography.Text>

            <MeterChips
              meters={form.meters}
              value={meter.id}
              onChange={form.selectMeter}
            />

            <Typography.Text variant="description" color="tertiary">
              {meter.tariff_zones === 2
                ? "Двухтарифный: день и ночь"
                : `Счётчик № ${meter.serial}`}
            </Typography.Text>

            {!meter.can_submit && (
              <Typography.Text variant="description" className={styles.Failed}>
                Срок поверки истёк - показания не примут, начисление пойдёт по
                нормативу. Поверку заказывают через УК
              </Typography.Text>
            )}
          </section>
        </Flex>

        {form.periods.length > 1 && (
          <Flex asChild align="stretch" direction="column" gap={12}>
            <section>
              <Typography.Text asChild variant="title" color="primary">
                <h2>За какой месяц?</h2>
              </Typography.Text>

              <div className={styles.Chips}>
                {form.periods.map((period) => (
                  <Button
                    key={period.period}
                    size="small"
                    variant={
                      period.period === form.period?.period
                        ? "primary"
                        : "secondary"
                    }
                    aria-pressed={period.period === form.period?.period}
                    onClick={() => form.selectPeriod(period.period)}
                  >
                    {formatPeriod(period.period)}
                  </Button>
                ))}
              </div>
            </section>
          </Flex>
        )}

        <Flex asChild align="stretch" direction="column" gap={8}>
          <section>
            <Flex align="baseline" gap={8}>
              <Typography.Text
                asChild
                variant="title"
                color="primary"
                className={styles.Grow}
              >
                <h2>Фото счётчика</h2>
              </Typography.Text>
              <Typography.Text variant="description" color="tertiary">
                обязательно
              </Typography.Text>
            </Flex>

            <PhotoStrip
              photos={form.photos.photos}
              isFull={form.photos.isFull}
              isUploading={form.photos.isUploading}
              onAdd={form.photos.add}
              onRemove={form.photos.remove}
            />

            <Typography.Text
              variant="description"
              color="tertiary"
              className={form.photos.isFailed ? styles.Failed : undefined}
            >
              {photoHint(form.photos)}
            </Typography.Text>
          </section>
        </Flex>

        <Flex asChild align="stretch" direction="column" gap={16}>
          <section>
            <Typography.Text asChild variant="title" color="primary">
              <h2>Показания, {METER_UNIT[meter.type]}</h2>
            </Typography.Text>

            <ReadingFields
              meter={meter}
              period={form.period.period}
              zones={form.zones}
              valueOf={form.valueOf}
              onChange={form.setValue}
            />
          </section>
        </Flex>

        {form.error && (
          <Typography.Text variant="description" className={styles.Failed}>
            {form.error}
          </Typography.Text>
        )}
      </div>

      <div className={styles.Footer}>
        <Button
          size="large"
          stretched
          loading={form.isSending}
          disabled={!form.canSend}
          onClick={form.send}
        >
          Отправить показания
        </Button>
      </div>
    </Panel>
  );
};

export const Component = MetersPage;
