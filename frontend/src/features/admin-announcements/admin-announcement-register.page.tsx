import {
  Button,
  CellSimple,
  Flex,
  Panel,
  Radio,
  Switch,
  Typography,
} from "@maxhub/max-ui";
import { useState } from "react";

import { errorMessage } from "@/shared/api/errors";
import { formatDayTime, formatShortDay, formatTime } from "@/shared/lib/format";
import { BottomSheet } from "@/shared/ui/bottom-sheet";
import { ErrorState, LoadingState } from "@/shared/ui/state";

import {
  chatLabel,
  isSending,
  noticeLabel,
  recipientLabel,
} from "./domain/labels";
import { useNoticeRegister } from "./model/use-notice-register";

import styles from "./admin-announcement-register.module.css";

const AdminAnnouncementRegisterPage = () => {
  const view = useNoticeRegister();
  const [isPicking, setIsPicking] = useState(false);

  if (view.isPending) {
    return <LoadingState fill title="Собираем реестр" />;
  }

  if (view.isError || !view.register) {
    return <ErrorState error={view.loadError} fill onRetry={view.retry} />;
  }

  const { register } = view;
  const { announcement } = register;
  const total = register.flats.length;
  const flatless = register.without_flat;

  return (
    <Panel className={styles.Page} mode="secondary">
      <div className={styles.Screen}>
        <Flex align="stretch" direction="column" gapY={4}>
          <Typography.Text asChild variant="title" color="primary">
            <h1>Реестр уведомлений</h1>
          </Typography.Text>

          <Typography.Text variant="description" color="secondary">
            Каким квартирам MAX доставил объявление в личные сообщения
          </Typography.Text>
        </Flex>

        <div className={styles.Panel}>
          {view.houses.length > 1 && (
            <CellSimple
              overline="Дом"
              title={register.address}
              showChevron
              onClick={() => setIsPicking(true)}
            />
          )}

          <CellSimple
            as="label"
            separator={view.houses.length > 1}
            title="Только без отметки"
            subtitle="Их нужно уведомить другим способом"
            after={
              <Switch
                checked={view.unmarkedOnly}
                onChange={(event) => view.setUnmarkedOnly(event.target.checked)}
              />
            }
          />
        </div>

        <Button
          size="large"
          stretched
          loading={view.pdf.isPending}
          disabled={view.pdf.isSuccess}
          onClick={view.sendPdf}
        >
          {view.pdf.isSuccess
            ? "Отправили в чат с ботом"
            : "Получить PDF в чат с ботом"}
        </Button>
        {view.pdf.error && (
          <Typography.Text variant="description" className={styles.Failed}>
            {errorMessage(
              view.pdf.error,
              "Не получилось отправить. Проверьте связь и попробуйте ещё раз",
            )}
          </Typography.Text>
        )}

        <Button
          size="large"
          variant="secondary"
          stretched
          onClick={() => window.print()}
        >
          Распечатать
        </Button>
      </div>

      <section className={styles.Sheet}>
        {register.is_demo && <p className={styles.Demo}>ДЕМО</p>}

        <h2 className={styles.Title}>Реестр уведомлений</h2>

        <p className={styles.Line}>{register.address}</p>

        <p className={styles.Quote}>
          Объявление от {formatDayTime(announcement.created_at)}: «
          {announcement.text}»
        </p>

        <p className={styles.Line}>
          <strong>
            Доставлено квартирам {register.flats_delivered} из {total}
          </strong>
          , без отметки {total - register.flats_delivered}
        </p>

        <p className={styles.Line}>
          {chatLabel(announcement, register.chat_delivered)}
        </p>

        {view.unmarkedOnly && (
          <p className={styles.Line}>Показаны только квартиры без отметки</p>
        )}

        {flatless.length > 0 && (
          <p className={styles.Line}>
            Жители без квартиры: доставлено{" "}
            {flatless.filter(({ status }) => status === "delivered").length} из{" "}
            {flatless.length}
          </p>
        )}

        <table className={styles.Table}>
          <thead>
            <tr>
              <th>Кв.</th>
              <th>Подъезд</th>
              <th>Статус</th>
              <th>Время</th>
            </tr>
          </thead>

          <tbody>
            {view.flats.map((flat) =>
              flat.recipients.length === 0 ? (
                <tr key={flat.flat_id} className={styles.Unmarked}>
                  <td>{flat.number}</td>
                  <td>{flat.entrance ?? "-"}</td>
                  <td>Нет в сервисе</td>
                  <td>-</td>
                </tr>
              ) : (
                flat.recipients.map((recipient, index) => (
                  <tr
                    key={`${flat.flat_id}-${index}`}
                    className={flat.delivered ? undefined : styles.Unmarked}
                  >
                    {index === 0 && (
                      <>
                        <td rowSpan={flat.recipients.length}>{flat.number}</td>
                        <td rowSpan={flat.recipients.length}>
                          {flat.entrance ?? "-"}
                        </td>
                      </>
                    )}
                    <td>
                      {noticeLabel(recipient.status, isSending(announcement))}
                      <span className={styles.Role}>
                        {recipientLabel(recipient)}
                      </span>
                    </td>
                    <td>
                      {recipient.at === null
                        ? "-"
                        : `${formatShortDay(recipient.at)} ${formatTime(recipient.at)}`}
                    </td>
                  </tr>
                ))
              ),
            )}
          </tbody>
        </table>

        {view.flats.length === 0 && (
          <p className={styles.Line}>
            {total === 0
              ? "В справочнике нет квартир этого дома"
              : "Сообщение дошло до всех квартир"}
          </p>
        )}

        <p className={styles.Note}>
          Реестр фиксирует доставку сообщения в MAX, прочтение MAX не сообщает.
          Квартиры без отметки нужно уведомить другим способом. Для собрания
          собственников реестр не заменяет заказное письмо
        </p>

        <p className={styles.Note}>
          Сформирован {formatDayTime(register.generated_at)}
          {register.is_demo && " · ДЕМО"}
        </p>
      </section>

      <BottomSheet isOpen={isPicking} onClose={() => setIsPicking(false)}>
        <Flex direction="column" align="stretch" gapY={12}>
          <Typography.Text asChild variant="title" color="primary">
            <h2 className={styles.SheetTitle}>Дом</h2>
          </Typography.Text>

          <div className={styles.Options}>
            {view.houses.map((house, index) => (
              <CellSimple
                key={house.id}
                as="label"
                separator={index > 0}
                title={house.address}
                after={
                  <Radio
                    name="register-house"
                    checked={house.id === register.house_id}
                    onChange={() => {
                      view.pickHouse(house.id);
                      setIsPicking(false);
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
            onClick={() => setIsPicking(false)}
          >
            Закрыть
          </Button>
        </Flex>
      </BottomSheet>
    </Panel>
  );
};

export const Component = AdminAnnouncementRegisterPage;
