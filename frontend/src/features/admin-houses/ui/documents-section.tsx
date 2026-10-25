import type { ChangeEvent } from "react";
import {
  Button,
  CellSimple,
  Flex,
  IconButton,
  Input,
  Typography,
} from "@maxhub/max-ui";

import { Card } from "@/shared/ui/card";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";
import { documentIcon, Icon, trashIcon } from "@/shared/ui/icon";
import { EmptyState, ErrorState, LoadingState } from "@/shared/ui/state";

import { houseDocumentFormConstraints } from "../domain/house-document";
import { useHouseDocuments } from "../model/use-house-documents";

import styles from "./documents-section.module.css";

export const DocumentsSection = ({ houseId }: { houseId: number }) => {
  const documents = useHouseDocuments(houseId);

  const pick = (event: ChangeEvent<HTMLInputElement>) => {
    const [file] = event.target.files ?? [];
    event.target.value = "";

    if (file) {
      documents.add(file);
    }
  };

  const list = () => {
    if (documents.isPending) {
      return <LoadingState title="Загружаем документы" />;
    }

    if (documents.isError) {
      return (
        <ErrorState
          error={documents.loadError}
          description="Не получилось загрузить документы. Проверьте связь и попробуйте ещё раз"
          onRetry={documents.retry}
        />
      );
    }

    if (documents.items.length === 0) {
      return (
        <EmptyState
          icon={documentIcon}
          title="Документов пока нет"
          description="Загрузите правила проживания, памятку или отчёт: жители дома откроют их из карточки дома"
        />
      );
    }

    return (
      <div className={styles.Panel}>
        {documents.items.map((document) => (
          <div key={document.id} className={styles.Row}>
            <CellSimple
              before={<Icon src={documentIcon} className={styles.CellIcon} />}
              title={document.title}
              asChild
            >
              <a href={document.url} target="_blank" rel="noreferrer" />
            </CellSimple>

            <IconButton
              variant="secondary"
              size="small"
              aria-label={`Удалить документ «${document.title}»`}
              onClick={() => documents.askRemove(document)}
            >
              <Icon src={trashIcon} size={20} />
            </IconButton>
          </div>
        ))}
      </div>
    );
  };

  return (
    <Flex asChild align="stretch" direction="column" gap={8}>
      <section>
        <Typography.Text asChild variant="title" color="primary">
          <h2 className={styles.Title}>Документы для жителей</h2>
        </Typography.Text>

        {list()}

        <Card>
          <Input
            placeholder="Название документа"
            maxLength={houseDocumentFormConstraints.titleMax}
            hint={documents.titleError}
            innerClassNames={{ hint: styles.Error }}
            {...documents.registerTitle()}
          />

          <Button asChild size="medium" variant="secondary">
            <label>
              <input
                type="file"
                accept="application/pdf"
                hidden
                disabled={documents.isAdding}
                onChange={pick}
              />
              {documents.isAdding ? "Загружаем документ…" : "Загрузить PDF"}
            </label>
          </Button>

          <Typography.Text
            variant="description"
            color={documents.addError ? undefined : "secondary"}
            className={documents.addError ? styles.Error : undefined}
          >
            {documents.addError ||
              "Без названия возьмём имя файла. Документ увидят только жители этого дома"}
          </Typography.Text>
        </Card>

        <ConfirmDialog
          isOpen={documents.removal.isOpen}
          title="Удалить документ?"
          description={`«${documents.removal.target?.title ?? ""}» пропадёт из карточки дома у жителей`}
          confirmLabel="Удалить"
          isPending={documents.isRemoving}
          error={documents.removeError}
          onConfirm={documents.confirmRemove}
          onClose={() => {
            if (!documents.isRemoving) {
              documents.removal.dismiss();
            }
          }}
        />
      </section>
    </Flex>
  );
};
