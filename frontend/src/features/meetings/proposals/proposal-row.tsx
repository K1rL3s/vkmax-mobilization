import type { ReactNode } from "react";
import { Button, Typography } from "@maxhub/max-ui";
import { generatePath, Link } from "react-router-dom";

import { Routes } from "@/shared/model/routes";
import { Card } from "@/shared/ui/card";
import { StatusPill } from "@/shared/ui/status-pill";

import {
  proposalDate,
  statusLabel,
  statusTone,
  type Proposal,
} from "./proposal";

import styles from "./proposal-row.module.css";

export const ProposalRow = ({
  proposal,
  actions,
}: {
  proposal: Proposal;
  actions?: ReactNode;
}) => (
  <Card>
    <div className={styles.Head}>
      <Typography.Text variant="description" color="secondary">
        {proposalDate(proposal)}
      </Typography.Text>

      <StatusPill tone={statusTone(proposal.status)}>
        {statusLabel(proposal.status)}
      </StatusPill>
    </div>

    <Typography.Text variant="body" color="primary">
      {proposal.text}
    </Typography.Text>

    {proposal.answer && (
      <Typography.Text
        className={styles.Answer}
        variant="description"
        color="secondary"
      >
        {proposal.answer}
      </Typography.Text>
    )}

    {proposal.poll_id !== null && (
      <Button asChild size="small" variant="secondary">
        <Link
          to={generatePath(Routes.MEETING, {
            pollId: String(proposal.poll_id),
          })}
        >
          Открыть опрос
        </Link>
      </Button>
    )}

    {actions && <div className={styles.Actions}>{actions}</div>}
  </Card>
);
