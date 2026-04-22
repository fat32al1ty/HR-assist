import * as React from 'react';
import { cn } from '@/lib/utils';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        ref={ref}
        className={cn(
          'w-full bg-[var(--color-surface-raised)] text-[var(--color-ink)]',
          'border border-[var(--color-border)] rounded-[var(--radius-md)]',
          'px-3.5 py-2.5 text-[var(--text-base)] font-[var(--font-body)]',
          'placeholder:text-[var(--color-ink-muted)]',
          'transition-[border-color,box-shadow] duration-[var(--duration-fast)]',
          'focus:outline-none focus:border-[var(--color-accent)] focus:shadow-[var(--shadow-focus)]',
          'disabled:opacity-55 disabled:cursor-not-allowed',
          className
        )}
        {...props}
      />
    );
  }
);
Input.displayName = 'Input';

export { Input };
