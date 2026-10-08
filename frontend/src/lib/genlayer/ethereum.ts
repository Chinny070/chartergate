/** Minimal EIP-1193 surface we rely on. Standard wallet RPC, not a GenLayer API. */
export interface InjectedProvider {
  request(args: { method: string; params?: unknown[] | object }): Promise<unknown>;
  on?(event: string, handler: (...args: never[]) => void): void;
  removeListener?(event: string, handler: (...args: never[]) => void): void;
}

declare global {
  interface Window {
    ethereum?: InjectedProvider;
  }
}

export function getInjectedProvider(): InjectedProvider | undefined {
  return typeof window === "undefined" ? undefined : window.ethereum;
}
