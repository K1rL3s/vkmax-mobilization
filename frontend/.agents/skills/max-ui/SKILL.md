---
name: max-ui
description: Библиотека React-компонентов MAX UI (@maxhub/max-ui) для мини-приложений MAX и standalone-приложений — установка, провайдер MaxUI, каталог компонентов с пропами, паттерны asChild и innerClassNames, готовые рецепты экранов. Использовать при написании любого кода на @maxhub/max-ui: вёрстка экранов, выбор подходящего компонента, подключение библиотеки, разбор ошибок вида "нет стилей" или "asChild не работает".
---

# MAX UI: использование библиотеки

`@maxhub/max-ui` — React-компоненты дизайн-системы MAX. Компоненты сами подстраиваются под iOS/Android и светлую/тёмную тему. Требуется React 19 (peer-зависимость), пакет поставляется только как ESM.

Живая документация с примерами: https://max-messenger.github.io/max-ui и https://dev.max.ru/ui

## Подключение

```sh
npm i @maxhub/max-ui
```

```tsx
import { createRoot } from 'react-dom/client';
import { MaxUI } from '@maxhub/max-ui';
import '@maxhub/max-ui/dist/styles.css';   // обязательно, иначе компоненты без стилей
import App from './App';

createRoot(document.getElementById('root')!).render(
  <MaxUI>
    <App />
  </MaxUI>
);
```

Провайдер `MaxUI` обязателен: он определяет платформу (по userAgent) и системную цветовую схему и выставляет на корневом `div` все CSS-переменные дизайн-системы. Переопределяется пропами:

```tsx
<MaxUI platform="android" colorScheme="dark" resetBody>…</MaxUI>
```

| Проп | Тип | По умолчанию |
| --- | --- | --- |
| `platform` | `'ios' \| 'android'` | детект по userAgent |
| `colorScheme` | `'light' \| 'dark'` | системная тема, с подпиской на изменения |
| `resetBody` | `boolean` | `false` — при `true` сбрасывает стили `body` |

Внутри приложения текущие значения доступны хуками `usePlatform()` и `useColorScheme()`.

## Какой компонент взять

| Задача | Компонент |
| --- | --- |
| Кнопка с текстом, иконками, счётчиком, лоадером | `Button` |
| Кнопка только с иконкой | `IconButton` |
| Группа строк/настроек | `CellList` + `CellSimple` / `CellAction` / `CellInput`, заголовок группы — `CellHeader` |
| Строка с заголовком, подписью, элементами слева и справа | `CellSimple` |
| Пункт-действие (меню, action sheet) | `CellAction` |
| Поле ввода внутри списка ячеек | `CellInput` |
| Отдельное поле ввода / многострочное | `Input` / `Textarea` |
| Переключатели | `Switch`, `Radio` |
| Аватар с фолбэком, статусом онлайн, бейджами в углах | `Avatar.Container` + `Avatar.Image` / `Avatar.Text` / `Avatar.Icon` / `Avatar.Overlay` / `Avatar.CloseButton` |
| Текст по дизайн-системе | `Typography.Text` (универсальный) или `Typography.Title` / `Headline` / `Body` / `Label` / `Action` / `Display` |
| Бейдж с числом | `Counter` |
| Индикатор загрузки | `Spinner` |
| Экран (фон, центрирование) | `Panel` |
| Раскладка | `Flex`, `Grid`, `Container` |
| Обрезка текста многоточием | `EllipsisText` |
| Своя кликабельная поверхность с нативным откликом | `Tappable` |

Все пропы, значения и дефолты — в **`references/catalog.md`**. Готовые куски экранов (профиль, список настроек, форма, состояние загрузки) — в **`references/recipes.md`**. Кастомизация внешнего вида — skill `max-ui-theming`.

## Паттерн 1: `asChild` вместо `as`

Компоненты полиморфны через `asChild`: компонент отдаёт свои стили и поведение единственному дочернему элементу.

```tsx
<Button asChild><a href="/next">Я — ссылка</a></Button>
<Button asChild><Link to="/home">Я — ссылка react-router</Link></Button>
<Typography.Title asChild><h1>Заголовок страницы</h1></Typography.Title>
<CellSimple title="Открыть профиль" showChevron asChild>
  <a href="https://example.com" target="_blank" rel="noreferrer" />
</CellSimple>
```

Правила:
- ребёнок должен быть ровно один React-элемент (внутри `Children.only`);
- при конфликте пропов `className`, `style` и `on*`-обработчики объединяются, остальное выигрывает родитель (`<Button disabled asChild><button disabled={false}/></Button>` → кнопка останется disabled);
- ARIA и блокировка клика при `disabled`/`loading` проставляются автоматически под фактический тег (`button`, `a`, либо `div role="button"`).

## Паттерн 2: `innerClassNames`

У составных компонентов классы внутренних элементов задаются типизированной картой — это легальная точка расширения, в отличие от селекторов по внутренним классам (они хешируются при сборке).

```tsx
<Button
  iconBefore={<MyIcon />}
  innerClassNames={{ iconBefore: 'my-icon', content: 'my-content' }}
>
  Отправить
</Button>
```

Ключи у каждого компонента свои и экспортированы типами (`ButtonInnerElementKey`, `CellSimpleInnerElementKey`, …) — см. каталог.

## Что ещё экспортирует пакет

- **Хуки**: `usePlatform`, `useColorScheme`, `useSystemColorScheme({ listenChanges })`, `useButtonLikeProps`, `useImageLoadingStatus({ src, referrerPolicy })`, `useCallbackRef`.
- **Хелперы**: `getSubtree`, `hasReactNode`, `mergeRefs` (`hasReactNode` удобен для собственных компонентов: отсекает `undefined`, `null`, `false`, `''`).
- **Иконки**, нужные самим компонентам: `Icon16Chevron`, `Icon16CloseIos`, `Icon16SearchOutline`, `Icon20CloseAndroid`, `Icon20CloseFilled`, `Icon24CloseAndroid`. Это не полноценный icon set — прикладные иконки берите свои.
- **Типы**: `PlatformType`, `ColorSchemeType`, `AsChildProp`, `InnerClassNamesProp<K>`, `MergeProps<A, B>`.
- **Реэкспорт Radix**: `Slot`, `Slottable`, `SlotProps` — чтобы делать свои компоненты с тем же `asChild`.

## Частые ошибки

| Симптом | Причина |
| --- | --- |
| Компоненты без стилей | не импортирован `@maxhub/max-ui/dist/styles.css` или нет обёртки `<MaxUI>` |
| Тема/платформа не применяются к части экрана | эта часть отрендерена вне поддерева `<MaxUI>` (портал, модалка в `document.body`) — оберните содержимое портала в свой `<MaxUI>` |
| `asChild` падает или теряет разметку | детей больше одного, либо ребёнок — не элемент (строка, фрагмент с несколькими узлами) |
| Клик срабатывает у `disabled`-ссылки | `disabled` ставится на `Button`, а не на вложенный `<a>` — проп должен быть на компоненте библиотеки |
| Кастомные стили «слетают» после обновления | цепляние за внутренние классы; используйте `className`, `innerClassNames` и CSS-переменные |
| Ошибки сборки при импорте пакета | пакет только ESM (`"type": "module"`), в CJS-окружении нужен бандлер или динамический `import()` |

Версионирование по SemVer, ломающие изменения токенов и пропов описаны в `docs/MIGRATION.md` репозитория библиотеки. Кастомизация не покрывается гарантиями совместимости между мажорными версиями.
