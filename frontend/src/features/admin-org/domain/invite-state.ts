import type { components } from "@/shared/api/schema/generated";

export type OrgInvite = components["schemas"]["OrgInviteItem"];

export type InviteState = "live" | "exhausted" | "expired" | "revoked";

export const inviteState = (invite: OrgInvite, now: number): InviteState => {
  if (invite.revoked_at !== null) return "revoked";
  if (Date.parse(invite.expires_at) <= now) return "expired";

  return invite.activations_used >= invite.max_activations
    ? "exhausted"
    : "live";
};

export const canRevoke = (state: InviteState) =>
  state === "live" || state === "exhausted";
