import { Flex, Panel, Typography } from "@maxhub/max-ui";

import styles from "./privacy.module.css";

const SECTIONS = [
  {
    title: "Какие данные мы обрабатываем",
    text: "Имя и идентификатор вашего профиля MAX, адрес дома и номер квартиры, лицевой счёт, номер телефона, если вы им поделились, а также содержание заявок: описание проблемы, фотографии и фотографии показаний счётчиков.",
  },
  {
    title: "Зачем",
    text: "Чтобы подать заявку в управляющую компанию вашего дома, передать показания счётчиков, показать начисления и учесть ваш голос в опросе жителей.",
  },
  {
    title: "Кому передаются данные",
    text: "Управляющей компании, которая обслуживает ваш дом, и назначенному ею исполнителю заявки - в объёме, необходимом для её выполнения. Другим жителям дома ваши данные не показываются: в результатах опроса видно только то, что квартира проголосовала.",
  },
  {
    title: "Сколько хранятся",
    text: "Пока вы пользуетесь сервисом. Вы можете отвязаться от дома в профиле - после этого доступ управляющей компании к вашим данным прекращается.",
  },
  {
    title: "Отзыв согласия",
    text: "Согласие можно отозвать, отвязавшись от всех домов в профиле или написав в управляющую компанию по контактам из карточки дома.",
  },
];

const PrivacyPage = () => {
  return (
    <Panel className={styles.Page}>
      <Flex
        className={styles.Content}
        align="stretch"
        direction="column"
        gap={20}
      >
        <Typography.Text asChild variant="header" color="primary">
          <h1>Политика обработки данных</h1>
        </Typography.Text>

        {SECTIONS.map((section) => (
          <Flex key={section.title} align="stretch" direction="column" gapY={4}>
            <Typography.Text variant="body-strong" color="primary">
              {section.title}
            </Typography.Text>

            <Typography.Text variant="description" color="secondary">
              {section.text}
            </Typography.Text>
          </Flex>
        ))}
      </Flex>
    </Panel>
  );
};

export const Component = PrivacyPage;
