import { Button, Flex } from "@maxhub/max-ui";
import { useLoaderData, useNavigate, useRevalidator } from "react-router-dom";

import { Consent } from "@/features/onboarding";
import { errorMessage } from "@/shared/api/errors";
import { getMaxLaunch, getWebApp } from "@/shared/lib/max";
import { Routes } from "@/shared/model/routes";
import { infoIcon } from "@/shared/ui/icon";
import { ErrorState, LoadingState, StateMessage } from "@/shared/ui/state";

import {
  ignoreDeeplink,
  retryDeeplink,
  type DeeplinkPageState,
} from "./deeplink-execution";

import styles from "./deeplink.module.css";

type FailureState = Extract<DeeplinkPageState, { status: "failure" }>;

const failureView = (state: FailureState) => {
  switch (state.kind) {
    case "flat":
      return {
        title: "Не получилось активировать код квартиры",
        description:
          "Возможно, код неверный или просрочен. Проверьте ссылку и попробуйте ещё раз",
        route: state.hasResidency ? Routes.HOME : Routes.ONBOARDING_HOUSE,
        action: state.hasResidency
          ? "Продолжить в текущий кабинет"
          : "Добавить недвижимость",
      };
    case "demo":
      return {
        title: "Демо-доступ пока не готов",
        description:
          "Проверьте связь и попробуйте ещё раз или продолжите без демо",
        route: state.hasResidency ? Routes.HOME : Routes.ONBOARDING_HOUSE,
        action: "Продолжить без демо",
      };
    default:
      return {
        title: "Не получилось добавить дом",
        description:
          "Возможно, дом не найден или временно нет связи. Вы можете выбрать его вручную",
        route: Routes.ONBOARDING_HOUSE,
        action: "Выбрать дом вручную",
      };
  }
};

const DeeplinkPage = () => {
  const state = useLoaderData() as DeeplinkPageState;
  const navigate = useNavigate();
  const revalidator = useRevalidator();

  if (revalidator.state !== "idle") {
    return <LoadingState fill />;
  }

  if (state.status === "consent") {
    return <Consent onContinue={() => revalidator.revalidate()} />;
  }

  if (state.status === "bot-only") {
    const continueInApp = () => {
      const raw = getMaxLaunch().startParam;

      if (raw) {
        ignoreDeeplink(raw);
      }

      navigate(state.hasResidency ? Routes.HOME : Routes.WELCOME, {
        replace: true,
      });
    };

    return (
      <StateMessage
        fill
        icon={infoIcon}
        title="Эту ссылку нужно открыть в боте"
        description="Вернитесь в чат с Жэкой Коммуналкиным и откройте ссылку там"
        action={
          <Flex className={styles.Actions} direction="column" gap={12}>
            <Button size="large" stretched onClick={() => getWebApp()?.close()}>
              Закрыть приложение
            </Button>

            <Button
              size="large"
              stretched
              variant="secondary"
              onClick={continueInApp}
            >
              Продолжить в приложении
            </Button>
          </Flex>
        }
      />
    );
  }

  if (state.status === "no-access") {
    return (
      <StateMessage
        fill
        icon={infoIcon}
        title="Нет доступа к кабинету УК"
        description="Эта ссылка для сотрудников управляющей компании, которая ведёт заявку"
        action={
          <Button
            size="large"
            onClick={() => navigate(state.route, { replace: true })}
          >
            На главную
          </Button>
        }
      />
    );
  }

  const retry = () => {
    const raw = getMaxLaunch().startParam;

    if (raw) {
      retryDeeplink(raw);
      revalidator.revalidate();
    }
  };

  const view = failureView(state);

  return (
    <Flex className={styles.Page} direction="column" justify="center">
      <ErrorState
        fill
        title={view.title}
        description={errorMessage(state.error, view.description)}
        onRetry={retry}
      />

      <Button
        size="large"
        stretched
        variant="secondary"
        onClick={() => navigate(view.route, { replace: true })}
      >
        {view.action}
      </Button>
    </Flex>
  );
};

export const Component = DeeplinkPage;
