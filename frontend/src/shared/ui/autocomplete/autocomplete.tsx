import { CellSimple, Flex, Input, Spinner, Typography } from "@maxhub/max-ui";

import { Icon } from "@/shared/ui/icon";
import { ErrorState } from "@/shared/ui/state";

import { Highlighted } from "./highlighted";

import styles from "./autocomplete.module.css";

export type AutocompleteOption = {
  id: number | string;
  title: string;
  subtitle?: string;
  icon?: string;
};

export type AutocompleteStatus = "idle" | "loading" | "error" | "ready";

type AutocompleteProps = {
  value: string;
  onChange: (value: string) => void;
  onSelect: (option: AutocompleteOption) => void;
  options: AutocompleteOption[];
  status: AutocompleteStatus;
  placeholder?: string;
  icon?: string;
  disabled?: boolean;
  inputMode?: "text" | "numeric";
  loadingText?: string;
  emptyTitle?: string;
  emptyDescription?: string;
  onRetry?: () => void;
};

export const Autocomplete = ({
  value,
  onChange,
  onSelect,
  options,
  status,
  placeholder,
  icon,
  disabled = false,
  inputMode = "text",
  loadingText = "Ищем…",
  emptyTitle = "Ничего не нашли",
  emptyDescription,
  onRetry,
}: AutocompleteProps) => {
  const isEmpty = status === "ready" && options.length === 0;

  return (
    <Flex align="stretch" direction="column" gap={8}>
      <Input
        placeholder={placeholder}
        inputMode={inputMode}
        disabled={disabled}
        iconBefore={
          icon && <Icon src={icon} size={20} className={styles.Icon} />
        }
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />

      {status !== "idle" && (
        <div className={styles.Dropdown}>
          {status === "loading" && (
            <Flex className={styles.Loading} align="center" gap={12}>
              <Spinner size={20} />
              <Typography.Text variant="body" color="secondary">
                {loadingText}
              </Typography.Text>
            </Flex>
          )}

          {status === "error" && <ErrorState onRetry={onRetry} />}

          {isEmpty && (
            <Flex
              className={styles.Empty}
              align="stretch"
              direction="column"
              gapY={4}
            >
              <Typography.Text variant="body-strong" color="primary">
                {emptyTitle}
              </Typography.Text>

              {emptyDescription && (
                <Typography.Text variant="description" color="secondary">
                  {emptyDescription}
                </Typography.Text>
              )}
            </Flex>
          )}

          {status === "ready" &&
            options.map((option) => (
              <CellSimple
                key={option.id}
                before={
                  option.icon && (
                    <Icon src={option.icon} className={styles.OptionIcon} />
                  )
                }
                title={<Highlighted text={option.title} query={value} />}
                subtitle={option.subtitle}
                onClick={() => onSelect(option)}
              />
            ))}
        </div>
      )}
    </Flex>
  );
};
