import { Button } from "@maxhub/max-ui";
import { generatePath, Link } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";

import type { AdminRequest } from "../domain/request-workflow";
import { useVisitCancel } from "../model/use-visit-cancel";

export const VisitActions = ({ request }: { request: AdminRequest }) => {
  const cancel = useVisitCancel(request.id);
  const proposeLabel = request.visit
    ? "Предложить другое время"
    : "Предложить время";

  return (
    <>
      {request.can_propose_visit && (
        <Button asChild size="medium" variant="secondary">
          <Link
            to={generatePath(Routes.ADMIN_REQUEST_VISIT, {
              requestId: String(request.id),
            })}
          >
            {proposeLabel}
          </Link>
        </Button>
      )}

      {request.visit && (
        <Button size="medium" variant="secondary" onClick={cancel.ask}>
          Отменить визит
        </Button>
      )}

      <ConfirmDialog
        isOpen={cancel.isOpen}
        title="Отменить визит?"
        description="Житель получит сообщение, что УК отменила визит. Выбранное им окно освободится"
        confirmLabel="Отменить визит"
        isPending={cancel.isPending}
        error={cancel.error}
        onConfirm={cancel.confirm}
        onClose={cancel.dismiss}
      />
    </>
  );
};
