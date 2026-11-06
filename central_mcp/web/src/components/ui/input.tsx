import type { InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/** Text or number input styled with design tokens (shadcn/ui Input). */
export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-9 w-full rounded-md border border-border bg-card px-3 text-sm",
        "focus-visible:outline-2 focus-visible:outline-primary",
        className,
      )}
      {...props}
    />
  );
}
