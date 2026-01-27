import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value: number | null | undefined): string {
  if (value == null || isNaN(value)) {
    return '$0.00';
  }
  if (value >= 1000) {
    return `$${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
  }
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatPercent(value: number, decimals: number = 1): string {
  return `${value.toFixed(decimals)}%`;
}

export function getHealthStatus(camPerOrder: number, target: number = 20): {
  status: string;
  color: string;
  bgColor: string;
} {
  if (camPerOrder >= target * 1.2) {
    return { status: 'EXCELLENT', color: 'text-green-600', bgColor: 'bg-green-50' };
  } else if (camPerOrder >= target) {
    return { status: 'HEALTHY', color: 'text-green-500', bgColor: 'bg-green-50' };
  } else if (camPerOrder >= target * 0.8) {
    return { status: 'CAUTION', color: 'text-yellow-600', bgColor: 'bg-yellow-50' };
  }
  return { status: 'CRITICAL', color: 'text-red-600', bgColor: 'bg-red-50' };
}
