import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  [
    'inline-flex items-center gap-1',
    'rounded-[var(--radius-full)] border px-2.5 py-0.5',
    'text-[11px] font-700 tracking-[0.05em] uppercase',
    'whitespace-nowrap leading-none',
  ],
  {
    variants: {
      variant: {
        default:  'bg-[var(--color-surface-muted)] text-[var(--color-ink-secondary)] border-[var(--color-border)]',
        accent:   'bg-[var(--color-accent-subtle)] text-[var(--color-accent)] border-[color-mix(in_srgb,var(--color-accent)_25%,transparent)]',
        success:  'bg-[var(--color-success-subtle)] text-[var(--color-success)] border-[color-mix(in_srgb,var(--color-success)_25%,transparent)]',
        warning:  'bg-[var(--color-warning-subtle)] text-[var(--color-warning)] border-[color-mix(in_srgb,var(--color-warning)_25%,transparent)]',
        danger:   'bg-[var(--color-danger-subtle)] text-[var(--color-danger)] border-[color-mix(in_srgb,var(--color-danger)_30%,transparent)]',
        info:     'bg-[var(--color-info-subtle)] text-[var(--color-info)] border-[color-mix(in_srgb,var(--color-info)_25%,transparent)]',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
