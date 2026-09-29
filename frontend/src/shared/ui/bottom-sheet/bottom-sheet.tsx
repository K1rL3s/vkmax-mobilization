import { useEffect, useRef, useState, type ReactNode } from "react";

import { cn } from "@/shared/lib/css";

import styles from "./bottom-sheet.module.css";

type BottomSheetProps = {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
  className?: string;
};

export const BottomSheet = ({
  isOpen,
  onClose,
  children,
  className,
}: BottomSheetProps) => {
  const dialog = useRef<HTMLDialogElement>(null);
  const [shown, setShown] = useState(children);

  if (isOpen && shown !== children) {
    setShown(children);
  }

  useEffect(() => {
    const element = dialog.current;

    if (!element) {
      return;
    }

    if (isOpen) {
      delete element.dataset.closing;
      element.inert = false;
      if (!element.open) {
        element.showModal();
      }
      return;
    }

    if (!element.open) {
      return;
    }

    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      element.close();
      return;
    }

    const finish = (event: AnimationEvent) => {
      if (event.target === element) {
        delete element.dataset.closing;
        element.close();
      }
    };

    element.dataset.closing = "";
    element.inert = true;
    element.addEventListener("animationend", finish);

    return () => element.removeEventListener("animationend", finish);
  }, [isOpen]);

  return (
    <dialog
      ref={dialog}
      className={cn(styles.BottomSheet, className)}
      onClose={onClose}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      {isOpen ? children : shown}
    </dialog>
  );
};
