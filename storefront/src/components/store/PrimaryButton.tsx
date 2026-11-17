import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Blue Panda button system.
 * - primary:   navy ink, turns brand blue on hover. The default purchase action.
 * - brand:     brand blue. Used once per view for the single most important action.
 * - secondary: outlined, for alternatives beside a primary.
 * - quiet:     text-only link-style action.
 */
type ButtonVariant = "primary" | "brand" | "secondary" | "quiet";
type ButtonSize = "md" | "lg";

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-ink text-white hover:bg-brand disabled:bg-surface-subtle disabled:text-muted",
  brand:
    "bg-brand text-white hover:bg-brand-hover disabled:bg-surface-subtle disabled:text-muted",
  secondary:
    "border border-line-strong bg-white text-ink hover:border-ink disabled:border-line disabled:bg-surface-subtle disabled:text-muted",
  quiet: "px-0 text-brand hover:text-brand-hover",
};

const sizes: Record<ButtonSize, string> = {
  md: "min-h-11 px-4 text-sm",
  lg: "min-h-12 px-6 text-[15px]",
};

const baseClassName =
  "bp-press inline-flex items-center justify-center gap-2 rounded-xl font-semibold disabled:cursor-not-allowed";

type PrimaryButtonProps = {
  children: ReactNode;
  className?: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
};

type PrimaryButtonLinkProps = PrimaryButtonProps &
  Omit<ComponentProps<typeof Link>, "className" | "children"> & {
    href: string;
  };

type PrimaryButtonNativeProps = PrimaryButtonProps &
  Omit<ComponentProps<"button">, "className" | "children">;

export function buttonClassName(
  variant: ButtonVariant = "primary",
  size: ButtonSize = "md",
  className?: string
) {
  return cn(baseClassName, sizes[size], variants[variant], className);
}

export function PrimaryButton({
  children,
  className,
  variant = "primary",
  size = "md",
  ...props
}: PrimaryButtonNativeProps) {
  return (
    <button {...props} className={buttonClassName(variant, size, className)}>
      {children}
    </button>
  );
}

export function PrimaryButtonLink({
  children,
  className,
  variant = "primary",
  size = "md",
  ...props
}: PrimaryButtonLinkProps) {
  return (
    <Link {...props} className={buttonClassName(variant, size, className)}>
      {children}
    </Link>
  );
}
