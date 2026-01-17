/**
 * Toast notification hook wrapping sonner
 *
 * Provides a consistent API for showing toast notifications across the app.
 * The Toaster component is already configured in app/layout.tsx.
 *
 * @example
 * ```tsx
 * const toast = useToast();
 *
 * // Simple notifications
 * toast.success("Position added successfully!");
 * toast.error("Failed to delete symbol");
 * toast.info("Refreshing data...");
 * toast.warning("Price data may be delayed");
 *
 * // Async operations with loading state
 * toast.promise(
 *   addSymbol({ symbol: "AAPL" }),
 *   {
 *     loading: "Adding AAPL to watchlist...",
 *     success: "AAPL added to watchlist",
 *     error: "Failed to add AAPL"
 *   }
 * );
 * ```
 */

import { toast as sonnerToast } from 'sonner'

export type ToastOptions = {
  description?: string
  duration?: number
  action?: {
    label: string
    onClick: () => void
  }
}

export type PromiseToastOptions<T> = {
  loading: string
  success: string | ((data: T) => string)
  error: string | ((error: Error) => string)
  description?: string
  duration?: number
}

/**
 * Custom hook wrapping sonner's toast API
 * Returns an object with helper methods for common toast patterns
 */
export function useToast() {
  return {
    /**
     * Show a success toast notification
     */
    success: (message: string, options?: ToastOptions) => {
      return sonnerToast.success(message, {
        description: options?.description,
        duration: options?.duration,
        action: options?.action,
      })
    },

    /**
     * Show an error toast notification
     */
    error: (message: string, options?: ToastOptions) => {
      return sonnerToast.error(message, {
        description: options?.description,
        duration: options?.duration,
        action: options?.action,
      })
    },

    /**
     * Show an info toast notification
     */
    info: (message: string, options?: ToastOptions) => {
      return sonnerToast.info(message, {
        description: options?.description,
        duration: options?.duration,
        action: options?.action,
      })
    },

    /**
     * Show a warning toast notification
     */
    warning: (message: string, options?: ToastOptions) => {
      return sonnerToast.warning(message, {
        description: options?.description,
        duration: options?.duration,
        action: options?.action,
      })
    },

    /**
     * Show a loading toast notification
     */
    loading: (message: string, options?: ToastOptions) => {
      return sonnerToast.loading(message, {
        description: options?.description,
        duration: options?.duration,
      })
    },

    /**
     * Show a toast for an async operation with loading, success, and error states
     * This is the recommended way to handle async operations
     */
    promise: <T>(promise: Promise<T>, options: PromiseToastOptions<T>) => {
      return sonnerToast.promise(promise, {
        loading: options.loading,
        success: (data: T) => {
          if (typeof options.success === 'function') {
            return options.success(data)
          }
          return options.success
        },
        error: (error: Error) => {
          if (typeof options.error === 'function') {
            return options.error(error)
          }
          return options.error
        },
        description: options.description,
        duration: options.duration,
      })
    },

    /**
     * Dismiss a specific toast or all toasts
     */
    dismiss: (toastId?: string | number) => {
      return sonnerToast.dismiss(toastId)
    },
  }
}
