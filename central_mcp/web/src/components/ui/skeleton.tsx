import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/** Pulsing placeholder shown while content loads (shadcn/ui Skeleton). */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden="true" className={cn("animate-pulse rounded-md bg-muted", className)} {...props} />;
}
