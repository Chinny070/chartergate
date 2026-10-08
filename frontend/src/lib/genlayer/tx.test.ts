import { describe, expect, it } from "vitest";
import { TransactionStatus } from "genlayer-js/types";
import { classifyError, phaseFromNetworkStatus } from "./tx";

describe("phaseFromNetworkStatus", () => {
  it("treats only FINALIZED as finalized", () => {
    expect(phaseFromNetworkStatus(TransactionStatus.FINALIZED)).toBe("finalized");
    expect(phaseFromNetworkStatus(TransactionStatus.ACCEPTED)).toBe("pending");
  });
  it("treats in-flight consensus statuses as pending", () => {
    for (const s of [
      TransactionStatus.PENDING,
      TransactionStatus.PROPOSING,
      TransactionStatus.COMMITTING,
      TransactionStatus.REVEALING,
      TransactionStatus.READY_TO_FINALIZE,
    ]) {
      expect(phaseFromNetworkStatus(s)).toBe("pending");
    }
  });
  it("fails closed on undetermined, canceled and timeouts", () => {
    for (const s of [
      TransactionStatus.UNDETERMINED,
      TransactionStatus.CANCELED,
      TransactionStatus.LEADER_TIMEOUT,
      TransactionStatus.VALIDATORS_TIMEOUT,
    ]) {
      expect(phaseFromNetworkStatus(s)).toBe("failed");
    }
  });
});

describe("classifyError", () => {
  it("detects wallet rejection by EIP-1193 code", () => {
    expect(classifyError({ code: 4001, message: "x" }).category).toBe("wallet_rejected");
  });
  it("falls back to unknown", () => {
    expect(classifyError(new Error("boom")).category).toBe("unknown");
  });
});
