import {
  createBrowserRouter,
  Outlet,
  RouterProvider,
  type To,
} from "react-router-dom";
import { App } from "./app";
import { protectedLoader } from "./protected-loader";
import { Providers } from "./providers";
import { TabBar } from "@/features/tab-bar";
import { useBackNavigation } from "@/shared/lib/max";
import { Routes } from "@/shared/model/routes";

const PushedScreen = ({ fallback }: { fallback: To }) => {
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
        children: [
          {
            path: Routes.WELCOME,
            lazy: () => import("@/features/onboarding/onboarding.page"),
          },
          {
            element: <PushedScreen fallback={Routes.WELCOME} />,
            children: [
              {
                path: Routes.ONBOARDING_HOUSE,
                lazy: () => import("@/features/onboarding/house-select.page"),
              },
            ],
          },
          {
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
