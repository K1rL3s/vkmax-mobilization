# Рецепты экранов на MAX UI

Готовые куски разметки под типовые задачи. Всё внутри предполагает, что приложение обёрнуто в `<MaxUI>` и подключён `@maxhub/max-ui/dist/styles.css`.

## Каркас экрана

```tsx
import { Panel, Container, Flex } from '@maxhub/max-ui';

<Panel mode="secondary">
  <Container>
    <Flex direction="column" gap={12}>
      {/* содержимое */}
    </Flex>
  </Container>
</Panel>
```

`Panel` — подложка экрана (`mode="secondary"` даёт «групповой» фон под островные списки), `centeredX` / `centeredY` центрируют содержимое — удобно для пустых состояний и заглушек. `Container` задаёт горизонтальные отступы контента, `Flex`/`Grid` — раскладку (`gap` числом трактуется как px).

## Шапка профиля

```tsx
import { Avatar, Container, Flex, Typography } from '@maxhub/max-ui';

<Container>
  <Flex direction="column" align="center" gap={8}>
    <Avatar.Container size={72} form="squircle" onlineStatus>
      <Avatar.Image src={user.photo} fallback={user.initials} fallbackGradient="blue" />
    </Avatar.Container>

    <Typography.Title variant="large-strong">{user.name}</Typography.Title>
    <Typography.Text variant="detail" color="secondary">{user.status}</Typography.Text>
  </Flex>
</Container>
```

`Avatar.Image` сам переключается на `Avatar.Text` с градиентом, если картинка не загрузилась — в `fallback` обычно кладут инициалы. Без картинки вовсе: `<Avatar.Container><Avatar.Text>ИИ</Avatar.Text></Avatar.Container>`.

## Список настроек

```tsx
import { CellHeader, CellList, CellSimple, Counter, Switch } from '@maxhub/max-ui';

<CellList mode="island" header={<CellHeader>Уведомления</CellHeader>}>
  <CellSimple
    surface="island"
    title="Пуши"
    subtitle="Звук и вибрация"
    before={<IconBell />}
    after={<Switch checked={push} onChange={(e) => setPush(e.target.checked)} />}
    separator
  />
  <CellSimple
    surface="island"
    title="Непрочитанные"
    before={<IconMail />}
    after={<Counter value={12} />}
    showChevron
    onClick={openUnread}
  />
</CellList>
```

- `mode="island"` — скруглённая группа с отступами, `mode="full-width"` — список во всю ширину (дефолт).
- `surface` у ячеек должен соответствовать режиму списка (`island` внутри островного списка).
- `separator` ставится у всех ячеек, кроме последней.
- Наличие `onClick` включает нажатие с платформенным откликом; `showChevron` добавляет шеврон справа.

## Навигация по ячейке

```tsx
import { CellSimple } from '@maxhub/max-ui';
import { Link } from 'react-router-dom';

<CellSimple title="Настройки" showChevron asChild>
  <Link to="/settings" />
</CellSimple>
```

Ссылка наружу — то же самое с `<a href target="_blank" rel="noreferrer" />`. Не используйте для навигации проп `link`: он рендерит внутри контента ячейки дополнительную строку-ссылку с текстом самого URL — это другой сценарий.

## Меню действий

```tsx
import { CellAction, CellList } from '@maxhub/max-ui';

<CellList mode="island">
  <CellAction surface="island" mode="primary" before={<IconShare />} onClick={share}>
    Поделиться
  </CellAction>
  <CellAction surface="island" mode="destructive" before={<IconTrash />} onClick={remove}>
    Удалить
  </CellAction>
</CellList>
```

`mode`: `primary`, `secondary`, `themed`, `destructive`, `custom`.

## Форма

```tsx
import { Button, Flex, Input, Textarea } from '@maxhub/max-ui';

<form onSubmit={handleSubmit}>
  <Flex direction="column" gap={12}>
    <Input
      placeholder="Имя"
      value={name}
      onChange={(e) => setName(e.target.value)}
      withClearButton
    />

    <Input
      placeholder="Промокод"
      mode="contrast"
      size="medium"
      iconBefore={<IconTag />}
      count={promo.length}
      hint="До 16 символов"
      value={promo}
      onChange={(e) => setPromo(e.target.value)}
    />

    <Textarea placeholder="Комментарий" rows={4} />

    <Button type="submit" stretched loading={isSubmitting}>
      Отправить
    </Button>
  </Flex>
</form>
```

`Input` — обычный контролируемый инпут: кнопка очистки эмулирует нативный ввод, поэтому `onChange` вызывается и при очистке. `loading` у кнопки сам блокирует клик и проставляет `aria-busy`.

## Поля внутри списка ячеек

```tsx
<CellList mode="island">
  <CellInput surface="island" before="Имя" placeholder="Введите имя" />
  <CellInput surface="island" before="Город" placeholder="Введите город" />
</CellList>
```

`CellInput` рендерит `label` с подписью `before` и полем; все нативные пропы (`value`, `onChange`, `placeholder`, `type`) уходят на `input`, `ref` ведёт на него же. Кнопка очистки включена по умолчанию.

## Группа радиокнопок

```tsx
<CellList mode="island">
  {options.map((option, index) => (
    <CellSimple
      key={option.value}
      surface="island"
      title={option.label}
      separator={index < options.length - 1}
      before={
        <Radio
          name="delivery"
          value={option.value}
          checked={value === option.value}
          onChange={() => setValue(option.value)}
        />
      }
      onClick={() => setValue(option.value)}
    />
  ))}
</CellList>
```

`Radio` и `Switch` — нативные инпуты со стилями ДС: группировка через общий `name`, состояние — вашим стейтом.

## Кнопки

```tsx
<Button variant="primary" size="large" stretched>Продолжить</Button>
<Button variant="secondary" iconBefore={<IconPlus />}>Добавить</Button>
<Button variant="ghost" indicator={<Counter value={3} />}>Входящие</Button>
<Button variant="destructive" size="small">Удалить</Button>
<IconButton variant="secondary" size="medium" aria-label="Закрыть"><Icon16CloseIos /></IconButton>
```

`indicator` с `Counter` внутри сам получает подходящий вариант под цвет кнопки — не задавайте ему `variant` вручную. Варианты `*-contrast` и `overlay` рассчитаны на тёмную или картиночную подложку. У `IconButton` всегда указывайте `aria-label`.

## Загрузка и пустое состояние

```tsx
import { Flex, Panel, Spinner, Typography } from '@maxhub/max-ui';

if (isLoading) {
  return (
    <Panel centeredX centeredY>
      <Spinner size={24} />
    </Panel>
  );
}

if (items.length === 0) {
  return (
    <Panel centeredX centeredY>
      <Flex direction="column" align="center" gap={8}>
        <Typography.Title variant="medium">Пока пусто</Typography.Title>
        <Typography.Text variant="detail" color="secondary">Добавьте первый элемент</Typography.Text>
      </Flex>
    </Panel>
  );
}
```

## Длинный текст

```tsx
import { EllipsisText } from '@maxhub/max-ui';

<EllipsisText maxLines={2}>{longText}</EllipsisText>
```

В `CellSimple` заголовок и подпись обрезаются сами — отдельный `EllipsisText` нужен только для собственной разметки.

## Свой компонент с тем же `asChild`

```tsx
import { Slot, type AsChildProp } from '@maxhub/max-ui';
import { type ComponentProps, forwardRef } from 'react';

interface CardProps extends ComponentProps<'div'>, AsChildProp {}

export const Card = forwardRef<HTMLDivElement, CardProps>(({ asChild, ...rest }, ref) => {
  const Comp = asChild ? Slot : 'div';
  return <Comp ref={ref} {...rest} />;
});
Card.displayName = 'Card';
```

## Реакция на платформу и тему

```tsx
import { Icon16CloseIos, Icon20CloseAndroid, IconButton, useColorScheme, usePlatform } from '@maxhub/max-ui';

const platform = usePlatform();       // 'ios' | 'android'
const colorScheme = useColorScheme(); // 'light' | 'dark'

<IconButton aria-label="Закрыть">
  {platform === 'ios' ? <Icon16CloseIos /> : <Icon20CloseAndroid />}
</IconButton>
```

Ветвить в JS стоит только разметку и ассеты: размеры, отступы, типографика и цвета уже различаются на уровне CSS-переменных — см. skill `max-ui-theming`.
