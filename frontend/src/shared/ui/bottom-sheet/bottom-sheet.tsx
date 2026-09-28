import { useEffect, useRef, type ReactNode } from "react";

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

  useEffect(() => {
    if (isOpen) {
      dialog.current?.showModal();
    } else {
      dialog.current?.close();
    }
  }, [isOpen]);

  return (
    <dialog
      ref={dialog}
      className={cn(styles.BottomSheet, className)}
      onClose={onClose}
    >
      {children}
    </dialog>
  );
};
