# Каталог компонентов MAX UI

Все компоненты принимают `ref` (через `forwardRef`) и нативные пропы своего корневого тега вдобавок к перечисленным. Дефолты указаны в скобках. Точный контракт всегда виден в `.d.ts` пакета и в Storybook: https://max-messenger.github.io/max-ui

## Провайдер

### `MaxUI` (корневой `div`)
| Проп | Тип | Описание |
| --- | --- | --- |
| `platform` | `'ios' \| 'android'` | по умолчанию определяется по userAgent |
| `colorScheme` | `'light' \| 'dark'` | по умолчанию системная тема с подпиской на изменения |
| `resetBody` | `boolean` (`false`) | вешает на `document.body` сбрасывающий класс |

Кладёт значения в `MaxUIContext`; читать их в компонентах — через `usePlatform()` / `useColorScheme()`.

## Действия

### `Button` (`button`, поддерживает `asChild`)
| Проп | Тип |
| --- | --- |
| `size` | `'xsmall' \| 'small' \| 'medium' \| 'large'` (`medium`) |
| `variant` | `'primary' \| 'secondary' \| 'ghost' \| 'primary-contrast' \| 'secondary-contrast' \| 'overlay' \| 'destructive'` (`primary`) |
| `stretched` | `boolean` (`false`) — ширина 100% |
| `iconBefore` / `iconAfter` | `ReactNode` |
| `indicator` | `ReactNode` — если это `<Counter />`, его `variant` автоматически подбирается под вариант кнопки |
| `loading` | `boolean` — показывает `Spinner`, прячет контент, проставляет `aria-busy`/`aria-disabled` |
| `innerClassNames` | ключи: `iconBefore`, `iconAfter`, `indicator`, `content`, `spinnerContainer`, `spinner` |

Размер и внешний вид спиннера подбираются автоматически под `size`/`variant`. На android нажатие даёт ripple, на ios — подсветку.

### `IconButton` (`button`, поддерживает `asChild`)
`size` (`'xsmall' | 'small' | 'medium' | 'large'`, дефолт `medium`), `variant` — те же значения, что у `Button` (`IconButtonVariant = ButtonVariant`, дефолт `primary`), `loading`, `disabled`. `innerClassNames`: `content`, `spinnerContainer`, `spinner`. Контент — одна иконка.

### `Tappable` (`as = 'div'`, поддерживает `asChild`)
Кликабельная поверхность с платформенным откликом: ripple на android, подсветка на ios. Пропы: `as` (корневой тег), `asChild`, `disabled`, `parentChildren`. Интерактивность определяется наличием `onClick`/`href`; на нём построены `CellSimple` и `CellAction`. В прикладном коде нужен, только если собираете собственную кликабельную поверхность в стилистике MAX.

### `SvgButton`
Кнопка-обёртка вокруг иконки без собственных размеров и фона (крестики очистки, закрытия).

## Ячейки и списки

### `CellList` (`div`)
| Проп | Тип |
| --- | --- |
| `mode` | `'full-width' \| 'island'` (`full-width`) |
| `filled` | `boolean` (по умолчанию `mode === 'island'`) |
| `header` | `ReactNode` — обычно `<CellHeader />` |

### `CellSimple` (`div` через `Tappable`, поддерживает `asChild` и `as`)
| Проп | Тип |
| --- | --- |
| `title` / `subtitle` / `overline` | `ReactNode` |
| `before` / `after` | `ReactNode` (слева / справа) |
| `height` | `'compact' \| 'normal'` (`normal`) |
| `surface` | `'default' \| 'island'` (`default`) |
| `subtitleMode` | `'secondary' \| 'tertiary'` (`secondary`) |
| `showChevron` | `boolean` (`false`) — `Icon16Chevron` справа |
| `separator` | `boolean` — разделитель под ячейкой |
| `disabled` | `boolean` (`false`) |
| `as` | `ElementType` (`div`) — корневой тег для `Tappable` |
| `link` | `string` — дополнительная ссылка внутри контента (`target="_blank"`), текстом выводится сам URL |
| `innerClassNames` | `before`, `after`, `chevron`, `content`, `title`, `subtitle`, `overline`, `link` |

`children` рендерятся внутри блока контента под `subtitle`. Тип собран как `MergeProps<ComponentProps<'div'>, CellSimpleOwnProps>`.

### `CellAction` (`button`, поддерживает `asChild`)
| Проп | Тип |
| --- | --- |
| `mode` | `'primary' \| 'secondary' \| 'themed' \| 'destructive' \| 'custom'` (`primary`) |
| `surface` | `'default' \| 'island'` (`default`) |
| `height` | `'compact' \| 'normal'` (`normal`) |
| `before` | `ReactNode` |
| `showChevron` | `boolean` (`false`) |
| `innerClassNames` | `before`, `chevron`, `content` |

### `CellHeader` (`div`)
`titleStyle` (`'caps' | 'normal'`, дефолт `caps`), `fullWidth` (`false`), `after`, `innerClassNames`: `content`, `after`.

### `CellInput` (корень — `label`, ref ведёт на `input`)
`height` (`normal`), `surface` (`default`), `before`, `innerClassNames`: `before`, `input`, `clearButton`, `body`. Остальные пропы уходят в `ClearableInput` → нативный `input` (`type="text"`), кнопка очистки включена по умолчанию.

## Поля ввода

### `Input` (`input`, `size` переопределён)
| Проп | Тип |
| --- | --- |
| `mode` | `'default' \| 'contrast'` (`default`) |
| `size` | `'large' \| 'medium'` (`large`) |
| `iconBefore` / `iconAfter` | `ReactNode` |
| `withClearButton` | `boolean` (`true`) — крестик очистки, когда поле не пустое |
| `count` | `number` — счётчик справа |
| `hint` | `ReactNode` — подпись под полем |
| `innerClassNames` | `container`, `input`, `clearButton`, `count`, `body`, `iconBefore`, `iconAfter`, `hint` |

### `Textarea` (`textarea`)
`mode` (`'primary' | 'secondary'`, дефолт `primary`), `innerClassNames`: `textarea`.

### `ClearableInput`
Низкоуровневый примитив, на котором построены `Input` и `CellInput`: `withClearButton` (`true`), `count`, `innerClassNames`: `input`, `clearButton`, `count`. Работает и в контролируемом, и в неконтролируемом режиме; очистка эмулирует нативный input-эвент, поэтому ваш `onChange` вызывается так же, как при ручном вводе.

### `Switch`, `Radio`
Нативные `input` (`Radio` — с фиксированным `type="radio"`), без собственных пропов; стилизация целиком на CSS.

## Аватары

`Avatar` — namespace, части импортируются как `Avatar.Container`, `Avatar.Image` и т.д.

| Часть | Пропы |
| --- | --- |
| `Avatar.Container` (`div`, `asChild`) | `size` (`16…96 \| number`, дефолт `40`), `form` (`'circle' \| 'squircle'`, дефолт `circle`), `onlineStatus` (`false`), `overlay`, `rightTopCorner`, `rightBottomCorner` (угол справа снизу игнорируется при `onlineStatus` и при размере ≤ 24), `innerClassNames`: `overlay`, `content`, `rightBottomCorner`, `rightTopCorner` |
| `Avatar.Image` (`img`) | `fallback: ReactNode`, `fallbackGradient` (`'red' \| 'orange' \| 'green' \| 'blue' \| 'purple' \| 'custom'`, дефолт `red`) — при ошибке загрузки рендерит `Avatar.Text` с этим градиентом |
| `Avatar.Text` (`span`) | `gradient` — те же значения; `custom` = задать фон самому |
| `Avatar.Icon`, `Avatar.Overlay` (`span`) | без собственных пропов |
| `Avatar.CloseButton` (`button`) | без собственных пропов |

Размер раздаётся частям через контекст контейнера, поэтому `Avatar.Image` / `Avatar.Text` / `Avatar.Icon` / `Avatar.Overlay` / `Avatar.CloseButton` используются только внутри `Avatar.Container`.

## Типографика

`Typography` — namespace: `Display`, `Headline`, `Title`, `Body`, `Label`, `Text`, `Action`. Все рендерят `span`, все поддерживают `asChild` (типичное применение — `<Typography.Title asChild><h1>…</h1></Typography.Title>`).

| Часть | `variant` (дефолт) |
| --- | --- |
| `Display` | нет вариантов |
| `Headline` | `'large-strong' \| 'medium' \| 'small' \| 'custom'` (`large-strong`) |
| `Title` | `'large-strong' \| 'medium' \| 'medium-strong' \| 'small' \| 'small-strong' \| 'custom'` (`large-strong`) |
| `Body` | `'large' \| 'large-strong' \| 'medium' \| 'medium-strong' \| 'small' \| 'small-strong' \| 'custom'` (`large-strong`) |
| `Label` | те же значения, что у `Body` (`large`) |
| `Action` | `'large' \| 'medium' \| 'small' \| 'xsmall' \| 'custom'` (`large`) |
| `Text` | `hero`, `header`, `subheader`, `title`, `body(-strong)`, `detail(-strong)`, `description(-strong)`, `label(-strong)`, `tag(-strong)`, `note(-strong)`, `action-large/medium/small/xsmall` (`body`); плюс `color`: `'primary' \| 'secondary' \| 'tertiary' \| 'inherit'` (`inherit`) |

`variant: 'custom'` отключает применение токенов — размер и вес задаёте сами.

## Индикаторы

### `Counter` (`span`)
`value: number` (обязателен, отображаемое число), `variant`: `'primary' | 'primary-contrast' | 'attention' | 'attention-contrast' | 'promo' | 'static' | 'static-contrast' | 'default' | 'mute' | 'menu'` (`primary`), `rounded: boolean`.

### `Spinner` (`span`)
`size`: `20 | 24 | number` (`20`), `appearance`: `'primary' | 'themed' | 'neutral-themed' | 'primary-static' | 'contrast' | 'contrast-static' | 'negative'` (`primary`). Под капотом сам выбирает ios- или android-вариант анимации.

## Раскладка

### `Panel` (`div`)
`mode`: `'primary' | 'secondary'` (`primary`), `centeredX`, `centeredY`. Экранная подложка.

### `Flex` (`div`, `asChild`)
`display` (`flex`), `direction` (`row`), `align` (`flex-start`), `justify` (`start`), `wrap`, `gap` / `gapX` / `gapY` (`number | string`; число трактуется как px через `getCssSizeValue`, значения уходят в `--MaxUi-Flex_gapX/gapY`).

### `Grid` (`div`, `asChild`)
`display` (`grid`), `align`, `justify`, `gap` / `gapX` / `gapY`, `cols`, `rows`.

### `Container` (`div`, `asChild`)
`fullWidth: boolean` — горизонтальные отступы контента экрана.

### `EllipsisText` (`span`, `asChild`)
`maxLines` (`1`); при `maxLines > 1` используется `-webkit-line-clamp`.

### `Ripple` (`span`)
Эффект нажатия для android; позиционируется абсолютно внутри кликабельного родителя, цвет задаётся переменной `--Ripple_backgroundColor`.
