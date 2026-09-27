import { Button, Input, Textarea, Typography } from "@maxhub/max-ui";
import { Navigate } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { ErrorState } from "@/shared/ui/state";

import { useVerifyMethod } from "./model/use-verify-method";

import styles from "./verify-method.module.css";

const VerifyMethodPage = () => {
  const form = useVerifyMethod();

  if (form.method === undefined || !form.residency) {
    return <Navigate to={Routes.HOME} replace />;
  }

  const isOrg = form.method === "org";
  const action = form.mismatched
    ? { label: "Отправить запрос в УК", run: form.askOrg }
    : { label: isOrg ? "Отправить запрос" : "Подтвердить", run: form.submit };

  const hint = () => {
    if (isOrg) {
      return "Номер есть в квитанции. Сотрудник УК проверит запрос вручную - ответ придёт в чат";
    }

    if (form.mismatched) {
      return "Проверьте номер в квитанции или отправьте запрос в УК - сотрудник проверит вручную";
    }

    return "Номер есть в квитанции. В демо-данных это номер квартиры с нулями до 10 цифр: для кв. 12 - 0000000012";
  };

  return (
    <div className={styles.Page}>
      <div className={styles.Content}>
        <Input
          placeholder="Лицевой счёт"
          inputMode="numeric"
          value={form.accountNo}
          onChange={(event) => form.setAccountNo(event.target.value)}
        />

        {isOrg && (
          <Textarea
            mode="secondary"
            placeholder="Комментарий (необязательно)"
            value={form.comment}
            onChange={(event) => form.setComment(event.target.value)}
          />
        )}

        {form.mismatched && (
          <Typography.Text variant="description" className={styles.Mismatch}>
            Лицевой счёт не совпал с кв. {form.residency.flat_number}
          </Typography.Text>
        )}

        <Typography.Text variant="description" color="secondary">
          {hint()}
        </Typography.Text>

        {form.isFailed && (
          <ErrorState
            title="Не получилось отправить"
            description="Проверьте связь и попробуйте ещё раз"
            error={form.failure}
            onRetry={form.submit}
          />
        )}
      </div>

      <div className={styles.Footer}>
        <Button
          size="large"
          stretched
          loading={form.isPending}
          disabled={form.isDisabled}
          onClick={action.run}
        >
          {action.label}
        </Button>
      </div>
    </div>
  );
};

export const Component = VerifyMethodPage;
