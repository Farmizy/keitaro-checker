import { type SelectHTMLAttributes, forwardRef } from "react"
import { cn } from "@/lib/utils"

const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => {
    return (
      <select
        className={cn(
          "flex h-9 w-full rounded-lg border border-border bg-muted/50 px-3 py-1 text-sm transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:border-primary/50 focus-visible:bg-muted/70 disabled:cursor-not-allowed disabled:opacity-50 [&>option]:bg-card [&>option]:text-card-foreground",
          className,
        )}
        ref={ref}
        {...props}
      >
        {children}
      </select>
    )
  },
)
Select.displayName = "Select"

export { Select }
