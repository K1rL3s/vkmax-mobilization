import {
  createBrowserRouter,
  Outlet,
  RouterProvider,
  type To,
} from "react-router-dom";
import { App } from "./app";
import { Component as ErrorPage } from "@/features/error/error.page";

import { protectedLoader } from "./protected-loader";
import { Providers } from "./providers";
import {
  onboardedLoader,
  sessionLoader,
  welcomeLoader,
} from "./session-loader";
import { TabBar } from "@/features/tab-bar";
import { useBackNavigation } from "@/shared/lib/max";
import { Routes } from "@/shared/model/routes";
import { LoadingState } from "@/shared/ui/state";

const PushedPage = ({ fallback }: { fallback: To }) => {
  useBackNavigation(fallback);

  return <Outlet />;
};

const router = createBrowserRouter([
  {
    element: (
      <Providers>
        <App />
      </Providers>
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
            element: <PushedPage fallback={Routes.WELCOME} />,
            children: [
              {
                path: Routes.PRIVACY,
                lazy: () => import("@/features/onboarding/privacy.page"),
              },
              {
                path: Routes.ONBOARDING_HOUSE,
                lazy: () => import("@/features/onboarding/house-select.page"),
              },
            ],
          },
          {
            loader: onboardedLoader,
            element: <PushedPage fallback={Routes.REQUESTS} />,
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
            element: <PushedPage fallback={Routes.HOME} />,
            children: [
              {
                path: Routes.METERS,
                lazy: () => import("@/features/meters/meters.page"),
              },
            ],
          },
          {
            element: <PushedPage fallback={Routes.HOME} />,
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
        ],
      },
      {
        path: Routes.OUTSIDE_MAX,
        lazy: () => import("@/features/outside-max/outside-max.page"),
      },
    ],
  },
]);

export const Router = () => {
  return <RouterProvider router={router} />;
};
