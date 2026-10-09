import { describe, expect, it, vi } from "vitest";

vi.mock("../../config/chain", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  CHARTERGATE_ADDRESS: "0x49990Cb776469F1363e1F06bD2870e0a5eCB374b",
}));

import { isTransientReadError, readView } from "./contract";
import type { ChainClient } from "./client";

const clientFailing = (errors: unknown[], value: unknown = "ok") => {
  const readContract = vi.fn(async () => {
    const next = errors.shift();
    if (next !== undefined) throw next;
    return value;
  });
  return { client: { readContract } as unknown as ChainClient, readContract };
};

describe("readView retries only transient network failures", () => {
  it("classifies errors", () => {
    expect(isTransientReadError(new Error("An unknown RPC error occurred. Details: Failed to fetch"))).toBe(true);
    expect(isTransientReadError(new Error("Rate limit exceeded: 30 requests per minute"))).toBe(true);
    expect(isTransientReadError(new Error("fetch failed"))).toBe(true);
    expect(isTransientReadError(new Error("Missing or invalid parameters. Details: execution failed"))).toBe(false);
    expect(isTransientReadError(new Error("EXPECTED:REVIEW_NOT_FOUND"))).toBe(false);
  });

  it("retries a transient failure and then returns the value", async () => {
    const { client, readContract } = clientFailing([new Error("Failed to fetch"), new Error("Failed to fetch")], 7);
    await expect(readView("get_review_count", [], client, [0, 0, 0])).resolves.toBe(7);
    expect(readContract).toHaveBeenCalledTimes(3);
  });

  it("gives up after the last delay and surfaces the error", async () => {
    const errors = [new Error("Failed to fetch"), new Error("Failed to fetch"), new Error("Failed to fetch")];
    const { client, readContract } = clientFailing(errors);
    await expect(readView("get_review_count", [], client, [0, 0])).rejects.toThrow("Failed to fetch");
    expect(readContract).toHaveBeenCalledTimes(3);
  });

  it("never retries a contract rejection", async () => {
    const { client, readContract } = clientFailing([new Error("execution failed")]);
    await expect(readView("get_review_for_proposal", [1], client, [0, 0, 0])).rejects.toThrow("execution failed");
    expect(readContract).toHaveBeenCalledTimes(1);
  });
});
