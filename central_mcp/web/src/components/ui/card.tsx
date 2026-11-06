import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/** Bordered surface used for listing cards and panels (shadcn/ui Card). */
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-xl border border-border bg-card text-card-foreground", className)} {...props} />;
}
