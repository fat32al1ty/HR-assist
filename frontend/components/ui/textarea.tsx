import * as React from 'react';
import { cn } from '@/lib/utils';

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        className={cn(
          'w-full min-h-[80px] resize-vertical',
          'bg-[var(--color-surface-raised)] text-[var(--color-ink)]',
          'border border-[var(--color-border)] rounded-[var(--radius-md)]',
          'px-3.5 py-2.5 text-[var(--text-base)] font-[var(--font-body)]',
          'placeholder:text-[var(--color-ink-muted)]',
          'leading-[var(--leading-normal)]',
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
Textarea.displayName = 'Textarea';

export { Textarea };
