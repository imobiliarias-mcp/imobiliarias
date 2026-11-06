import { useEffect, useRef, type ReactNode } from "react";

interface FilterDrawerProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

/** Full-screen filter sheet for small screens, built on a native modal dialog. */
export function FilterDrawer({ open, onClose, children }: FilterDrawerProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) {
      return;
    }
    if (open && !dialog.open) {
      dialog.showModal();
    }
    if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      className="m-0 h-dvh max-h-none w-full max-w-none bg-card p-0 text-card-foreground md:hidden"
    >
      <div className="flex h-full flex-col">
        <header className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-base font-semibold">Filtros</h2>
          <button type="button" onClick={onClose} className="min-h-11 min-w-11 rounded-md px-3 hover:bg-muted">
            Fechar
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-4 py-4 pb-[max(1rem,env(safe-area-inset-bottom))]">{children}</div>
      </div>
    </dialog>
  );
}
