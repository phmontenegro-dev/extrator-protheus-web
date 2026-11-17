import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Helper padrão shadcn para combinar classes Tailwind, resolvendo conflitos:
 *   cn("px-2 py-1", condicao && "px-4") → "py-1 px-4"
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
