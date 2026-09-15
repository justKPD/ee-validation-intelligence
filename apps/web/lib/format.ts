export const pct = (v: number | null | undefined, digits = 1): string =>
  v === null || v === undefined ? "—" : `${(v * 100).toFixed(digits)}%`;

export const num = (v: number | null | undefined, digits = 0): string =>
  v === null || v === undefined ? "—" : v.toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: digits });

export const score = (v: number | null | undefined): string => (v === null || v === undefined ? "—" : v.toFixed(3));

export const label = (key: string): string => key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export const shortHash = (h: string): string => `${h.slice(0, 8)}…${h.slice(-6)}`;
