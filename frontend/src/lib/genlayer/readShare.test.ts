import { beforeEach, describe, expect, it, vi } from "vitest";

const readView = vi.fn();
vi.mock("./contract", () => ({ readView: (...a: unknown[]) => readView(...a), submitWrite: vi.fn() }));

import { getEvidenceCount } from "./charterGate";

describe("identical in-flight reads share one request", () => {
  beforeEach(() => readView.mockReset());

  it("collapses concurrent identical reads into a single RPC call", async () => {
    readView.mockResolvedValue(3n);
    const [a, b] = await Promise.all([getEvidenceCount(), getEvidenceCount()]);
    expect(a).toBe(3);
    expect(b).toBe(3);
    expect(readView).toHaveBeenCalledTimes(1);
  });

  it("does not cache once the read settles: a later read asks again", async () => {
    readView.mockResolvedValue(3n);
    await getEvidenceCount();
    await getEvidenceCount();
    expect(readView).toHaveBeenCalledTimes(2);
  });

  it("a failed read is not remembered", async () => {
    readView.mockRejectedValueOnce(new Error("Failed to fetch")).mockResolvedValueOnce(4n);
    await expect(getEvidenceCount()).rejects.toThrow("Failed to fetch");
    await expect(getEvidenceCount()).resolves.toBe(4);
  });
});
