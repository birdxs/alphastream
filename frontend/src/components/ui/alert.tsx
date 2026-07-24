// Input: variant: "default" | "destructive" | "warn" | "degraded", children
// Output: Alert 提示组件（含错误/警告/降级语义）
// Pos: UI 基础组件；S-UI-3 错误/降级统一入口
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const alertVariants = cva(
  "relative w-full rounded-lg border px-4 py-3 text-sm [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg]:text-foreground [&>svg~*]:pl-7",
  {
    variants: {
      variant: {
        default: "bg-background text-foreground",
        destructive:
          "border-destructive/50 text-destructive dark:border-destructive [&>svg]:text-destructive",
        /* S-UI-3：配额告警 / 非致命警告 */
        warn:
          "border-[color:var(--warn,#D97706)]/40 bg-[color:var(--warn,#D97706)]/10 text-[color:var(--warn,#B45309)] dark:text-[color:var(--warn,#FBBF24)] [&>svg]:text-current",
        /* S-UI-3：上游降级 / 部分可用 */
        degraded:
          "border-amber-500/30 bg-amber-500/5 text-amber-800 dark:text-amber-300 [&>svg]:text-current",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

const Alert = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof alertVariants>
>(({ className, variant, ...props }, ref) => (
  <div
    ref={ref}
    role="alert"
    className={cn(alertVariants({ variant }), className)}
    {...props}
  />
));
Alert.displayName = "Alert";

const AlertTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h5
    ref={ref}
    className={cn("mb-1 font-medium leading-none tracking-tight", className)}
    {...props}
  />
));
AlertTitle.displayName = "AlertTitle";

const AlertDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("text-sm [&_p]:leading-relaxed", className)}
    {...props}
  />
));
AlertDescription.displayName = "AlertDescription";

export { Alert, AlertTitle, AlertDescription };
