import {
  Button,
  CellAction,
  CellSimple,
  IconButton,
  Panel,
  Typography,
} from "@maxhub/max-ui";
import { useNavigate } from "react-router-dom";

import {
  confirmationCaption,
  residencyState,
} from "@/features/flat-confirmation";
import { cn } from "@/shared/lib/css";
import { Routes } from "@/shared/model/routes";
import { type Residency } from "@/shared/model/session";
import { closeIcon, homeIcon, Icon, plusIcon } from "@/shared/ui/icon";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import { IconTile } from "@/shared/ui/icon-tile";

import { useResidencySwitcher } from "./use-residency-switcher";
import { useUnlink } from "./use-unlink";

import styles from "./residencies.module.css";

const flatOf = (residency: Residency) => {
  const caption = confirmationCaption(residencyState(residency));

  return residency.flat_number == null
    ? caption
    : `кв. ${residency.flat_number} · ${caption}`;
};

const ResidenciesPage = () => {
  const navigate = useNavigate();
  const switcher = useResidencySwitcher();
  const unlink = useUnlink();

  return (
    <Panel className={styles.Page} mode="secondary">
      <div className={styles.Content}>
        <div className={styles.Panel}>
          {switcher.residencies.map((residency, index) => {
            const isMarked = switcher.isMarked(residency);

            return (
              <CellSimple
                key={residency.resident_id}
                className={cn(isMarked && styles.marked)}
                separator={index > 0}
                before={
                  <IconTile
                    icon={homeIcon}
                    tone={isMarked ? "themed" : "neutral"}
                  />
                }
                title={residency.address}
                subtitle={flatOf(residency)}
                after={
                  <IconButton
                    size="xsmall"
                    variant="ghost"
                    aria-label={`Отвязаться от дома ${residency.address}`}
                    onClick={(event) => {
                      event.stopPropagation();
                      unlink.ask(residency);
                    }}
                  >
                    <Icon src={closeIcon} size={18} className={styles.Close} />
                  </IconButton>
                }
                onClick={() => switcher.mark(residency)}
              />
            );
          })}

          <CellAction
            mode="primary"
            before={<Icon src={plusIcon} />}
            onClick={() => void navigate(Routes.ONBOARDING_HOUSE)}
          >
            Добавить дом
          </CellAction>
        </div>

        <Typography.Text
          variant="description"
          color="tertiary"
          className={styles.Note}
        >
          Заявки, показания и опросы кабинет показывает для выбранного адреса
        </Typography.Text>
      </div>

      <div className={styles.Footer}>
        <Button
          size="large"
          stretched
          loading={switcher.isSwitching}
          disabled={!switcher.marked}
          onClick={() => void switcher.confirm()}
        >
          Подтвердить
        </Button>
      </div>

      <ConfirmDialog
        isOpen={unlink.isOpen}
        title="Отвязаться от дома?"
        description={
          <>
            Заявки и показания останутся. Чтобы указать другую квартиру,
            привяжитесь к дому заново.
            {unlink.target?.verified &&
              " Подтверждение квартиры при этом слетит - получать его придётся снова."}
          </>
        }
        confirmLabel="Отвязаться"
        error={
          unlink.isFailed &&
          "Не получилось отвязаться. Проверьте связь и попробуйте ещё раз"
        }
        isPending={unlink.isPending}
        onConfirm={unlink.submit}
        onClose={unlink.cancel}
      />
    </Panel>
  );
};

export const Component = ResidenciesPage;
