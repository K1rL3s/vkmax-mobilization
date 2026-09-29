import { MaxUI } from "@maxhub/max-ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { useIsPresent } from "motion/react";
import {
  createBrowserRouter,
  Outlet,
  redirect,
  RouterProvider,
} from "react-router-dom";
import { App } from "./app";
import { Component as ErrorPage } from "@/features/error/error.page";

import { protectedLoader } from "./protected-loader";
import { deeplinkLoader } from "./deeplink-loader";
import {
  adminLoader,
  onboardedLoader,
  sessionLoader,
  welcomeLoader,
} from "./session-loader";
import { AdminTabBar } from "@/features/admin-tab-bar";
import { TabBar } from "@/features/tab-bar";
import { queryClient } from "@/shared/api/query-client";
import { useBackNavigation } from "@/shared/lib/max";
import { Routes } from "@/shared/model/routes";
import { LoadingState } from "@/shared/ui/state";

const PushedPage = () => {
  useBackNavigation(useIsPresent());

  return <Outlet />;
};

const router = createBrowserRouter([
  {
    element: (
      <MaxUI resetBody>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </MaxUI>
    ),
    children: [
      {
        loader: protectedLoader,
        errorElement: <ErrorPage />,
        hydrateFallbackElement: <LoadingState fill />,
        children: [
          {
            path: Routes.WELCOME,
            loader: welcomeLoader,
            lazy: () => import("@/features/onboarding/onboarding.page"),
          },
          {
            path: Routes.DEEPLINK,
            loader: deeplinkLoader,
            lazy: () => import("@/features/deeplink/deeplink.page"),
          },
          {
            element: <PushedPage />,
            children: [
              {
                path: Routes.PRIVACY,
                lazy: () => import("@/features/onboarding/privacy.page"),
              },
              {
                path: Routes.ONBOARDING_HOUSE,
                lazy: () => import("@/features/onboarding/house-select.page"),
              },
              {
                path: Routes.REGISTER,
                loader: sessionLoader,
                lazy: () =>
                  import("@/features/org-registration/org-registration.page"),
              },
            ],
          },
          {
            loader: onboardedLoader,
            element: <PushedPage />,
            children: [
              {
                path: Routes.REQUEST_NEW,
                lazy: () => import("@/features/new-request/new-request.page"),
              },
              {
                path: Routes.REQUEST,
                lazy: () => import("@/features/request/request.page"),
              },
            ],
          },
          {
            loader: onboardedLoader,
            element: <PushedPage />,
            children: [
              {
                path: Routes.MEETING,
                lazy: () => import("@/features/meetings/poll.page"),
              },
              {
                path: Routes.MEETING_NON_VOTERS,
                lazy: () => import("@/features/meetings/non-voters.page"),
              },
              {
                path: Routes.MEETING_NEW,
                lazy: () => import("@/features/meetings/new-poll.page"),
              },
              {
                path: Routes.MEETING_INITIATIVE_NEW,
                lazy: () => import("@/features/meetings/new-initiative.page"),
              },
            ],
          },
          {
            loader: onboardedLoader,
            element: <PushedPage />,
            children: [
              {
                path: Routes.FLAT,
                lazy: () => import("@/features/flat/flat.page"),
              },
              {
                path: Routes.METERS,
                lazy: () => import("@/features/meters/meters.page"),
              },
              {
                path: Routes.RESIDENCIES,
                lazy: () => import("@/features/residencies/residencies.page"),
              },
              {
                path: Routes.ANNOUNCEMENTS,
                lazy: () =>
                  import("@/features/announcements/announcements.page"),
              },
              {
                path: Routes.FAQ,
                lazy: () => import("@/features/faq/faq.page"),
              },
              {
                path: Routes.EMERGENCY,
                lazy: () => import("@/features/emergency/emergency.page"),
              },
              {
                path: Routes.HOUSE_PROBLEMS,
                lazy: () =>
                  import("@/features/house-problems/house-problems.page"),
              },
            ],
          },
          {
            loader: onboardedLoader,
            element: <PushedPage />,
            children: [
              {
                path: Routes.CHARGES,
                lazy: () => import("@/features/charges/charges.page"),
              },
              {
                path: Routes.CHARGE,
                lazy: () => import("@/features/charges/charge.page"),
              },
            ],
          },
          {
            loader: onboardedLoader,
            element: <PushedPage />,
            children: [
              {
                path: Routes.HOUSE_CARD,
                lazy: () => import("@/features/house-card/house-card.page"),
              },
              {
                path: Routes.NOTIFICATIONS,
                lazy: () => import("@/features/profile/notifications.page"),
              },
              {
                path: Routes.APPEARANCE,
                lazy: () => import("@/features/profile/appearance.page"),
              },
            ],
          },
          {
            loader: onboardedLoader,
            element: <PushedPage />,
            children: [
              {
                path: Routes.APPOINTMENTS,
                lazy: () => import("@/features/appointments/appointments.page"),
              },
              {
                path: Routes.HOUSE_MAP,
                lazy: () => import("@/features/house-map/house-map.page"),
              },
            ],
          },
          {
            loader: onboardedLoader,
            element: <PushedPage />,
            children: [
              {
                path: Routes.APPOINTMENT,
                lazy: () => import("@/features/appointments/appointment.page"),
              },
            ],
          },
          {
            element: <PushedPage />,
            children: [
              {
                path: Routes.FLAT_CONFIRMATION,
                loader: sessionLoader,
                lazy: () =>
                  import("@/features/flat-confirmation/flat-confirmation.page"),
              },
              {
                path: Routes.FLAT_CONFIRMATION_METHOD,
                loader: sessionLoader,
                lazy: () =>
                  import("@/features/flat-confirmation/verify-method.page"),
              },
            ],
          },
          {
            loader: onboardedLoader,
            handle: "tabs",
            element: (
              <>
                <Outlet />
                <TabBar />
              </>
            ),
            children: [
              {
                path: Routes.HOME,
                lazy: () => import("@/features/home/home.page"),
              },
              {
                path: Routes.REQUESTS,
                lazy: () => import("@/features/request-list/request-list.page"),
              },
              {
                path: Routes.MEETINGS,
                lazy: () => import("@/features/meetings/meetings.page"),
              },
              {
                path: Routes.PROFILE,
                lazy: () => import("@/features/profile/profile.page"),
              },
            ],
          },
          {
            loader: adminLoader,
            children: [
              {
                path: Routes.ADMIN,
                loader: () => redirect(Routes.ADMIN_REQUESTS),
              },
              {
                handle: "tabs",
                element: (
                  <>
                    <Outlet />
                    <AdminTabBar />
                  </>
                ),
                children: [
                  {
                    path: Routes.ADMIN_REQUESTS,
                    lazy: () =>
                      import("@/features/admin-requests/admin-requests.page"),
                  },
                  {
                    path: Routes.ADMIN_ANNOUNCEMENTS,
                    lazy: () =>
                      import("@/features/admin-announcements/admin-announcements.page"),
                  },
                  {
                    path: Routes.ADMIN_POLLS,
                    lazy: () =>
                      import("@/features/admin-polls/admin-polls.page"),
                  },
                  {
                    path: Routes.ADMIN_RECEPTION,
                    lazy: () =>
                      import("@/features/admin-reception/admin-reception.page"),
                  },
                  {
                    path: Routes.ADMIN_HOUSES,
                    lazy: () =>
                      import("@/features/admin-houses/admin-houses.page"),
                  },
                  {
                    path: Routes.ADMIN_ANALYTICS,
                    lazy: () =>
                      import("@/features/admin-analytics/admin-analytics.page"),
                  },
                ],
              },
              {
                element: <PushedPage />,
                children: [
                  {
                    path: Routes.ADMIN_REQUEST,
                    lazy: () =>
                      import("@/features/admin-requests/admin-request.page"),
                  },
                  {
                    path: Routes.ADMIN_REQUEST_PHONE,
                    lazy: () =>
                      import("@/features/admin-requests/admin-request-phone.page"),
                  },
                  {
                    path: Routes.ADMIN_REQUEST_GROUP,
                    lazy: () =>
                      import("@/features/admin-requests/admin-request-group.page"),
                  },
                ],
              },
              {
                element: <PushedPage />,
                children: [
                  {
                    path: Routes.ADMIN_ANNOUNCEMENT_NEW,
                    lazy: () =>
                      import("@/features/admin-announcements/admin-announcement-new.page"),
                  },
                  {
                    path: Routes.ADMIN_ANNOUNCEMENT_REGISTER,
                    lazy: () =>
                      import("@/features/admin-announcements/admin-announcement-register.page"),
                  },
                ],
              },
              {
                element: <PushedPage />,
                children: [
                  {
                    path: Routes.ADMIN_POLL,
                    lazy: () =>
                      import("@/features/admin-polls/admin-poll.page"),
                  },
                  {
                    path: Routes.ADMIN_POLL_NEW,
                    lazy: () =>
                      import("@/features/admin-polls/admin-poll-new.page"),
                  },
                ],
              },
              {
                element: <PushedPage />,
                children: [
                  {
                    path: Routes.ADMIN_ACCESS,
                    lazy: () =>
                      import("@/features/admin-reception/admin-access.page"),
                  },
                  {
                    path: Routes.ADMIN_ACCESS_NEW,
                    lazy: () =>
                      import("@/features/admin-reception/admin-access-new.page"),
                  },
                ],
              },
              {
                element: <PushedPage />,
                children: [
                  {
                    path: Routes.ADMIN_HOUSE,
                    lazy: () =>
                      import("@/features/admin-houses/admin-house.page"),
                  },
                  {
                    path: Routes.ADMIN_HOUSE_QR,
                    lazy: () =>
                      import("@/features/admin-houses/admin-house-qr.page"),
                  },
                  {
                    path: Routes.ADMIN_VERIFICATIONS,
                    lazy: () =>
                      import("@/features/admin-verifications/admin-verifications.page"),
                  },
                  {
                    path: Routes.ADMIN_ORG,
                    lazy: () => import("@/features/admin-org/admin-org.page"),
                  },
                  {
                    path: Routes.ADMIN_ORG_INVITES,
                    lazy: () =>
                      import("@/features/admin-org/admin-org-invites.page"),
                  },
                ],
              },
              {
                element: <PushedPage />,
                children: [
                  {
                    path: Routes.ADMIN_VERIFICATION,
                    lazy: () =>
                      import("@/features/admin-verifications/admin-verification.page"),
                  },
                ],
              },
              {
                element: <PushedPage />,
                children: [
                  {
                    path: Routes.ADMIN_BENCHMARK,
                    lazy: () =>
                      import("@/features/admin-analytics/admin-benchmark.page"),
                  },
                ],
              },
            ],
          },
        ],
      },
      {
        path: Routes.OUTSIDE_MAX,
        lazy: () => import("@/features/outside-max/outside-max.page"),
      },
    ],
  },
]);

export const Router = () => <RouterProvider router={router} />;
