import {
  AnimatePresence,
  domAnimation,
  LazyMotion,
  m,
  MotionConfig,
  useIsPresent,
  usePresenceData,
  type Variants,
} from "motion/react";
import { useContext, useState, type ReactNode } from "react";
import {
  type NavigationType,
  UNSAFE_DataRouterStateContext as DataRouterStateContext,
  UNSAFE_LocationContext as LocationContext,
  useMatches,
  useNavigationType,
  useOutlet,
} from "react-router-dom";

import { cn } from "@/shared/lib/css";

import styles from "./screen-transition.module.css";

const variants: Variants = {
  enter: (type: NavigationType) =>
    type === "PUSH"
      ? { y: window.innerHeight }
      : { opacity: type === "POP" ? 0.6 : 0 },
  shown: { y: 0, opacity: 1 },
  leave: (type: NavigationType) =>
    type === "POP"
      ? { y: window.innerHeight }
      : { opacity: type === "PUSH" ? 0.6 : 0 },
};

const Screen = ({
  type,
  children,
}: {
  type: NavigationType;
  children: ReactNode;
}) => {
  const isPresent = useIsPresent();
  const leaveType: NavigationType = usePresenceData();
  const [scroll, setScroll] = useState<number>();

  if (!isPresent && scroll === undefined) {
    setScroll(window.scrollY);
  }

  if (isPresent && scroll !== undefined) {
    setScroll(undefined);
  }

  return (
    <m.div
      className={cn(
        styles.Screen,
        scroll !== undefined && styles.leaving,
        (isPresent ? type !== "POP" : leaveType === "POP") && styles.front,
      )}
      style={
        scroll === undefined
          ? undefined
          : { top: -scroll, clipPath: `inset(${scroll}px 0 0 0)` }
      }
      custom={type}
      variants={variants}
      initial="enter"
      animate="shown"
      exit="leave"
      transition={{ duration: 0.24, ease: [0.32, 0.72, 0, 1] }}
    >
      {children}
    </m.div>
  );
};

export const ScreenTransition = () => {
  const outlet = useOutlet();
  const location = useContext(LocationContext);
  const routerState = useContext(DataRouterStateContext);
  const type = useNavigationType();
  const tabs = useMatches().find((match) => match.handle === "tabs");

  return (
    <LazyMotion features={domAnimation} strict>
      <MotionConfig reducedMotion="user">
        <AnimatePresence initial={false} custom={type}>
          <Screen key={tabs?.id ?? location.location.pathname} type={type}>
            <LocationContext value={location}>
              <DataRouterStateContext value={routerState}>
                {outlet}
              </DataRouterStateContext>
            </LocationContext>
          </Screen>
        </AnimatePresence>
      </MotionConfig>
    </LazyMotion>
  );
};
