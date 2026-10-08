export const sameAddress = (a?: string | null, b?: string | null) =>
  !!a && !!b && a.toLowerCase() === b.toLowerCase();

export const shortAddress = (a: string) => `${a.slice(0, 6)}…${a.slice(-4)}`;
