import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { TxState } from "./tx";
import { watchTransaction } from "./watch";

type Tx = Record<string, unknown>;
const fixturePath = fileURLToPath(new URL("./__fixtures__/live-txs.json", import.meta.url));
const fixtures = JSON.parse(readFileSync(fixturePath, "utf-8")) as Record<string, { tx: Tx }>;
const live = (name: string): Tx => structuredClone(fixtures[name].tx);
const HASH = ("0x" + "cd".repeat(32)) as `0x${string}`;

/** A scripted network: each call returns (or throws) the next item. */
function scripted(items: (Tx | Error)[]) {
  let i = 0;
  const calls: number[] = [];
  const slept: number[] = [];
  return {
    calls,
    slept,
    deps: {
      getTransaction: async () => {
        calls.push(i);
        const item = items[Math.min(i++, items.length - 1)];
        if (item instanceof Error) throw item;
        return item;
      },
      sleep: async (ms: number) => {
        slept.push(ms);
      },
    },
  };
}
const status = (name: string, statusName: string): Tx => ({ ...live(name), statusName });
const run = async (items: (Tx | Error)[], opts = {}) => {
  const net = scripted(items);
  const emitted: TxState[] = [];
  const final = await watchTransaction(HASH, net.deps, (s) => emitted.push(s), opts);
  return { net, emitted, final };
};

describe("watchTransaction", () => {
  it("reports pending as the network progresses, then finalized only after successful execution", async () => {
    const ok = "live_success_update_section";
    const { emitted, final, net } = await run([
      status(ok, "PENDING"),
      status(ok, "PROPOSING"),
      status(ok, "ACCEPTED"),
      live(ok),
    ]);
    expect(emitted.map((s) => `${s.phase}:${s.networkStatus}`)).toEqual([
      "pending:PENDING",
      "pending:PROPOSING",
      "pending:ACCEPTED",
      "finalized:FINALIZED",
    ]);
    expect(final.phase).toBe("finalized");
    expect(net.calls.length).toBe(4);
  });

  it("does not repeat identical pending states", async () => {
    const ok = "live_success_update_section";
    const { emitted } = await run([status(ok, "PENDING"), status(ok, "PENDING"), status(ok, "PENDING"), live(ok)]);
    expect(emitted.map((s) => s.phase)).toEqual(["pending", "finalized"]);
  });

  it("waits one interval before the first read, so SUBMITTED stays visible until the network knows the tx", async () => {
    const { net } = await run([live("live_success_update_section")], { intervalMs: 1234 });
    expect(net.slept[0]).toBe(1234);
  });

  it("a FINALIZED rollback ends as failed, never finalized (the Stage 1.2 bug)", async () => {
    const { emitted, final } = await run([status("live_rollback_not_owner", "PENDING"), live("live_rollback_not_owner")]);
    expect(final.phase).toBe("failed");
    expect(final.failure?.code).toBe("EXPECTED:NOT_OWNER");
    expect(emitted.some((s) => s.phase === "finalized")).toBe(false);
  });

  it("stops immediately on CANCELED instead of polling until a retry limit", async () => {
    const { net, final } = await run([status("live_success_update_section", "CANCELED")], { maxPolls: 100 });
    expect(final.phase).toBe("failed");
    expect(final.failure?.category).toBe("consensus");
    expect(net.calls.length).toBe(1);
  });

  it("stops immediately on UNDETERMINED", async () => {
    const { net, final } = await run([status("live_success_update_section", "UNDETERMINED")]);
    expect(final.phase).toBe("failed");
    expect(net.calls.length).toBe(1);
  });

  it("tolerates transient read errors, then continues to the real result", async () => {
    const { final, net } = await run([new Error("fetch failed"), new Error("fetch failed"), live("live_success_update_section")]);
    expect(final.phase).toBe("finalized");
    expect(net.calls.length).toBe(3);
  });

  it("gives up after too many consecutive read errors and surfaces the error", async () => {
    const { final } = await run([new Error("getaddrinfo ENOTFOUND")], { maxConsecutiveErrors: 3, maxPolls: 50 });
    expect(final.phase).toBe("failed");
    expect(final.failure?.category).toBe("unknown");
    expect(final.failure?.debug).toContain("ENOTFOUND");
    expect(final.failure?.message).toContain("check the transaction hash");
  });

  it("a successful read resets the consecutive-error count", async () => {
    const ok = "live_success_update_section";
    const e = new Error("blip");
    const { final } = await run([e, e, status(ok, "PENDING"), e, e, live(ok)], { maxConsecutiveErrors: 3 });
    expect(final.phase).toBe("finalized");
  });

  it("times out as failed (with a 'may still complete' message) when it never becomes final", async () => {
    const { final, net } = await run([status("live_success_update_section", "PENDING")], { maxPolls: 4, intervalMs: 3000 });
    expect(final.phase).toBe("failed");
    expect(final.failure?.category).toBe("timeout");
    expect(final.failure?.message).toContain("may still complete");
    expect(net.calls.length).toBe(4);
  });

  it("an unreadable terminal response fails closed", async () => {
    const { final } = await run([{ statusName: "FINALIZED", result: 6 }]);
    expect(final.phase).toBe("failed");
    expect(final.failure?.category).toBe("unrecognized");
  });
});
