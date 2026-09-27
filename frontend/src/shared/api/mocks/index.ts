import { adminAnalyticsConfigs } from "./admin-analytics";
import { adminAnnouncementsConfigs } from "./admin-announcements";
import { adminHousesConfigs } from "./admin-houses";
import { adminOrgConfigs } from "./admin-org";
import { adminPollsConfigs } from "./admin-polls";
import { adminReceptionConfigs } from "./admin-reception";
import { adminRequestsConfigs } from "./admin-requests";
import { adminVerificationsConfigs } from "./admin-verifications";
import { announcementsConfigs } from "./announcements";
import { appointmentsConfigs } from "./appointments";
import { chargesConfigs } from "./charges";
import { flatInvitesConfigs } from "./flat-invites";
import { flatsConfigs } from "./flats";
import { housesConfigs } from "./houses";
import { meConfigs } from "./me";
import { metersConfigs } from "./meters";
import { notificationsConfigs } from "./notifications";
import { orgsConfigs } from "./orgs";
import { pollsConfigs } from "./polls";
import { requestsConfigs } from "./requests";

export const mockConfigs = [
  ...meConfigs,
  ...housesConfigs,
  ...flatsConfigs,
  ...metersConfigs,
  ...requestsConfigs,
  ...pollsConfigs,
  ...chargesConfigs,
  ...flatInvitesConfigs,
  ...notificationsConfigs,
  ...appointmentsConfigs,
  ...announcementsConfigs,
  ...adminRequestsConfigs,
  ...adminAnnouncementsConfigs,
  ...adminPollsConfigs,
  ...adminReceptionConfigs,
  ...adminHousesConfigs,
  ...adminVerificationsConfigs,
  ...adminAnalyticsConfigs,
  ...adminOrgConfigs,
  ...orgsConfigs,
];
