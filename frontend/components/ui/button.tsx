'use client';

import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  // Base
  [
    'inline-flex items-center justify-center gap-2 whitespace-nowrap',
    'font-semibold leading-none tracking-tight',
    'rounded-[var(--radius-md)]',
    'transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--duration-fast)]',
    'focus-visible:outline-2 focus-visible:outline-[var(--color-focus-ring)] focus-visible:outline-offset-2',
    'disabled:opacity-55 disabled:cursor-not-allowed',
    'active:translate-y-[1px]',
    'select-none',
  ],
  {
    variants: {
      variant: {
        primary: [
          'bg-[var(--color-accent)] text-[var(--color-on-accent)]',
          'shadow-[var(--shadow-sm)]',
          'hover:bg-[var(--color-accent-hover)] hover:shadow-[var(--shadow-md)]',
        ],
        secondary: [
          'bg-[var(--color-surface-raised)] text-[var(--color-ink)]',
          'border border-[var(--color-border)]',
          'hover:bg-[var(--color-surface-muted)] hover:border-[var(--color-border-strong)]',
        ],
        ghost: [
          'bg-transparent text-[var(--color-ink)]',
          'hover:bg-[var(--color-surface-muted)] hover:text-[var(--color-ink)]',
        ],
        danger: [
          'bg-[var(--color-danger-subtle)] text-[var(--color-danger)]',
          'border border-[color-mix(in_srgb,var(--color-danger)_30%,transparent)]',
          'hover:bg-[color-mix(in_srgb,var(--color-danger)_12%,transparent)]',
        ],
        link: [
          'bg-transparent text-[var(--color-accent)] underline underline-offset-[3px]',
          'hover:text-[var(--color-accent-hover)]',
          'p-0 h-auto',
        ],
      },
      size: {
        sm:  'h-8  px-3  text-[var(--text-sm)]',
        md:  'h-11 px-4  text-[var(--text-base)]',
        lg:  'h-13 px-6  text-[var(--text-lg)]',
        icon:'h-9  w-9   p-0',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  }
);
Button.displayName = 'Button';

export { Button, buttonVariants };
