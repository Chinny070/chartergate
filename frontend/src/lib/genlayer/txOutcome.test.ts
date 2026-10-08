import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { classifyTransaction, describeContractError, describeOutcomeLine, readExecutionOutcome } from "./tx";

/**
 * Fixtures in __fixtures__/live-txs.json are REAL genlayer-js 1.1.8 `getTransaction()` results from
 * StudioNet (chain 61999), pruned to the fields the transaction layer reads.
 *   LIVE:    live_success_*, live_rollback_*, live_contract_error_typeerror (used unmodified)
 *   DERIVED: any case that changes `statusName`/`result`/etc. on a live fixture, because that
 *            terminal status could not be captured from the live network on demand.
 */
type Tx = Record<string, unknown>;
const fixturePath = fileURLToPath(new URL("./__fixtures__/live-txs.json", import.meta.url));
const fixtures = JSON.parse(readFileSync(fixturePath, "utf-8")) as Record<string, { _hash: string; tx: Tx }>;
const live = (name: string): Tx => structuredClone(fixtures[name].tx);
const HASH = ("0x" + "ab".repeat(32)) as `0x${string}`;

const withStatus = (tx: Tx, statusName: string): Tx => ({ ...tx, statusName });

describe("live fixtures are what we think they are", () => {
  it("StudioNet leaves the typed txExecutionResultName undefined (the reason leader receipts are read)", () => {
    for (const name of Object.keys(fixtures).filter((n) => n.startsWith("live_"))) {
      expect(fixtures[name].tx.txExecutionResultName).toBeUndefined();
    }
  });
  it("every live fixture is consensus-FINALIZED with a MAJORITY_AGREE result (number 6)", () => {
    for (const name of Object.keys(fixtures).filter((n) => n.startsWith("live_"))) {
      expect(fixtures[name].tx.statusName).toBe("FINALIZED");
      expect(fixtures[name].tx.result).toBe(6);
    }
  });
});

describe("FINALIZED + execution SUCCESS => finalized successfully", () => {
  for (const name of ["live_success_update_section", "live_success_deploy"]) {
    it(`${name} (LIVE)`, () => {
      const s = classifyTransaction(live(name), HASH);
      expect(s.phase).toBe("finalized");
      expect(s.failure).toBeUndefined();
      expect(s.networkStatus).toBe("FINALIZED");
      expect(s.consensusResult).toBe("MAJORITY_AGREE");
      expect(s.execution).toEqual({ kind: "success" });
    });
  }
});

describe("FINALIZED + rollback => failed (never a green finalization)", () => {
  it("non-owner write: EXPECTED:NOT_OWNER (LIVE)", () => {
    const s = classifyTransaction(live("live_rollback_not_owner"), HASH);
    expect(s.phase).toBe("failed");
    expect(s.phase).not.toBe("finalized");
    expect(s.failure?.category).toBe("rolled_back");
    expect(s.failure?.code).toBe("EXPECTED:NOT_OWNER");
    expect(s.failure?.message).toBe("Only the contract owner can do this.");
    expect(s.execution).toEqual({ kind: "rolled_back", code: "EXPECTED:NOT_OWNER" });
  });

  it("keeps consensus finality and execution outcome as separate facts", () => {
    const s = classifyTransaction(live("live_rollback_not_owner"), HASH);
    expect(s.networkStatus).toBe("FINALIZED");
    expect(s.consensusResult).toBe("MAJORITY_AGREE");
    expect(s.execution?.kind).toBe("rolled_back");
    expect(describeOutcomeLine(s)).toBe(
      "network FINALIZED · consensus MAJORITY_AGREE · execution ROLLED BACK (EXPECTED:NOT_OWNER)",
    );
  });

  it("deterministic EXPECTED error with an argument name (LIVE)", () => {
    const s = classifyTransaction(live("live_rollback_invalid_type"), HASH);
    expect(s.phase).toBe("failed");
    expect(s.failure?.code).toBe("EXPECTED:INVALID_TYPE:section_id");
    expect(s.failure?.message).toBe('The value for "section_id" has the wrong type.');
  });

  it("raw contract crash (Stage 1.1 TypeError): failed, no stack trace in the user message (LIVE)", () => {
    const s = classifyTransaction(live("live_contract_error_typeerror"), HASH);
    expect(s.phase).toBe("failed");
    expect(s.failure?.category).toBe("contract_error");
    expect(s.failure?.message).not.toMatch(/Traceback|File "|TypeError/);
    expect(s.failure?.message).toContain("No changes were made");
    // ...but the technical detail is kept internally for debugging.
    expect(s.failure?.debug).toMatch(/Traceback/);
    expect(s.execution?.kind).toBe("contract_error");
  });

  it("rollback detail never leaks into the success path: a rollback payload that contains the word SUCCESS", () => {
    const tx = live("live_rollback_not_owner");
    (tx.consensus_data as { leader_receipt: { result: { payload: string } }[] }).leader_receipt[0].result.payload =
      "EXPECTED:SUCCESS";
    expect(classifyTransaction(tx, HASH).phase).toBe("failed");
  });
});

describe("transactions that are not final are never success (DERIVED statuses)", () => {
  it("PENDING => pending", () => {
    const s = classifyTransaction(withStatus(live("live_success_update_section"), "PENDING"), HASH);
    expect(s.phase).toBe("pending");
    expect(s.networkStatus).toBe("PENDING");
    expect(s.execution).toBeUndefined();
  });

  for (const status of ["PROPOSING", "COMMITTING", "REVEALING", "READY_TO_FINALIZE", "APPEAL_REVEALING", "APPEAL_COMMITTING"]) {
    it(`${status} => pending`, () => {
      expect(classifyTransaction(withStatus(live("live_success_update_section"), status), HASH).phase).toBe("pending");
    });
  }

  it("ACCEPTED + successful execution is still pending: accepted is inside the appeal window, not final", () => {
    const s = classifyTransaction(withStatus(live("live_success_update_section"), "ACCEPTED"), HASH);
    expect(s.phase).toBe("pending");
    expect(s.phase).not.toBe("finalized");
  });
});

describe("terminal consensus failures => failed (DERIVED statuses)", () => {
  for (const status of ["CANCELED", "UNDETERMINED", "LEADER_TIMEOUT", "VALIDATORS_TIMEOUT"]) {
    it(`${status} => failed (consensus)`, () => {
      // Even though the underlying fixture shows a successful leader execution, a non-final-success
      // consensus status must not be reported as success.
      const s = classifyTransaction(withStatus(live("live_success_update_section"), status), HASH);
      expect(s.phase).toBe("failed");
      expect(s.failure?.category).toBe("consensus");
      expect(s.failure?.message).toContain(status);
    });
  }

  it("FINALIZED but validators did not agree => failed, even if the leader executed successfully", () => {
    for (const result of [2, 3, 4, 5, 7]) {
      const s = classifyTransaction({ ...live("live_success_update_section"), result }, HASH);
      expect(s.phase, `result=${result}`).toBe("failed");
      expect(s.failure?.category).toBe("consensus");
    }
  });

  it("FINALIZED with no consensus result at all => failed", () => {
    const tx = live("live_success_update_section");
    delete tx.result;
    expect(classifyTransaction(tx, HASH).phase).toBe("failed");
  });
});

describe("malformed or unrecognised responses fail closed", () => {
  const ok = () => live("live_success_update_section");

  for (const [label, value] of [
    ["null", null],
    ["undefined", undefined],
    ["a string", "FINALIZED"],
    ["a number", 7],
    ["an array", []],
    ["an empty object", {}],
  ] as const) {
    it(`${label} => failed (unrecognized)`, () => {
      const s = classifyTransaction(value, HASH);
      expect(s.phase).toBe("failed");
      expect(s.failure?.category).toBe("unrecognized");
    });
  }

  it("unknown lifecycle status => failed", () => {
    const s = classifyTransaction(withStatus(ok(), "BANANA"), HASH);
    expect(s.phase).toBe("failed");
    expect(s.failure?.category).toBe("unrecognized");
  });

  it("status given only as a number is understood (7 = FINALIZED); an unknown number fails", () => {
    const tx = ok();
    delete tx.statusName;
    expect(classifyTransaction({ ...tx, status: 7 }, HASH).phase).toBe("finalized");
    expect(classifyTransaction({ ...tx, status: 99 }, HASH).phase).toBe("failed");
  });

  it("FINALIZED + agreement but no consensus_data => failed (cannot confirm success)", () => {
    const tx = ok();
    delete tx.consensus_data;
    const s = classifyTransaction(tx, HASH);
    expect(s.phase).toBe("failed");
    expect(s.failure?.category).toBe("unrecognized");
  });

  it("FINALIZED + agreement but no entry with mode 'leader' => failed", () => {
    const tx = ok();
    (tx.consensus_data as { leader_receipt: { mode: string }[] }).leader_receipt.forEach((r) => (r.mode = "validator"));
    expect(classifyTransaction(tx, HASH).phase).toBe("failed");
  });

  it("execution_result SUCCESS but result.status is not 'return' => failed", () => {
    const tx = ok();
    (tx.consensus_data as { leader_receipt: { result: { status: string } }[] }).leader_receipt[0].result.status = "rollback";
    expect(classifyTransaction(tx, HASH).phase).toBe("failed");
  });

  it("the SDK's own declared shape (result as a string) is not trusted => failed", () => {
    const tx = ok();
    (tx.consensus_data as { leader_receipt: { result: unknown }[] }).leader_receipt[0].result = "success";
    expect(classifyTransaction(tx, HASH).phase).toBe("failed");
  });

  it("unrecognised execution_result strings => failed", () => {
    for (const value of ["success", "OK", "", "PENDING", 1, null]) {
      const tx = ok();
      (tx.consensus_data as { leader_receipt: { execution_result: unknown }[] }).leader_receipt[0].execution_result = value;
      expect(classifyTransaction(tx, HASH).phase, JSON.stringify(value)).toBe("failed");
    }
  });

  it("execution ERROR with an unknown result.status => failed", () => {
    const tx = live("live_rollback_not_owner");
    (tx.consensus_data as { leader_receipt: { result: { status: string } }[] }).leader_receipt[0].result.status = "mystery";
    const s = classifyTransaction(tx, HASH);
    expect(s.phase).toBe("failed");
    expect(s.failure?.category).toBe("unrecognized");
  });

  it("readExecutionOutcome never throws on garbage", () => {
    for (const junk of [undefined, null, 1, "x", [], {}, { consensus_data: 1 }, { consensus_data: { leader_receipt: "no" } }]) {
      expect(() => readExecutionOutcome(junk)).not.toThrow();
      expect(readExecutionOutcome(junk).kind).toBe("unrecognized");
    }
  });
});

describe("typed txExecutionResultName path (non-Studio chains; DERIVED)", () => {
  const base = () => live("live_success_update_section");
  it("FINISHED_WITH_RETURN => success", () => {
    expect(classifyTransaction({ ...base(), txExecutionResultName: "FINISHED_WITH_RETURN" }, HASH).phase).toBe("finalized");
  });
  it("FINISHED_WITH_ERROR => failed, even if a leader receipt looks successful", () => {
    const s = classifyTransaction({ ...base(), txExecutionResultName: "FINISHED_WITH_ERROR" }, HASH);
    expect(s.phase).toBe("failed");
    expect(s.failure?.category).toBe("rolled_back");
  });
  it("NOT_VOTED and unknown values => failed", () => {
    for (const v of ["NOT_VOTED", "WHATEVER", 1]) {
      expect(classifyTransaction({ ...base(), txExecutionResultName: v }, HASH).phase).toBe("failed");
    }
  });
});

describe("describeContractError", () => {
  it("maps the contract's stable codes", () => {
    expect(describeContractError("EXPECTED:NOT_OWNER")).toBe("Only the contract owner can do this.");
    expect(describeContractError("EXPECTED:INVALID_TYPE:body")).toBe('The value for "body" has the wrong type.');
    expect(describeContractError("EXPECTED:INTEGER_OUT_OF_RANGE:offset")).toBe('The value for "offset" is out of range.');
    expect(describeContractError("EXPECTED:SECTION_ID_EXISTS")).toBe("The contract rejected the transaction: SECTION_ID_EXISTS.");
  });
  it("handles empty and unexpected codes without exposing huge text", () => {
    expect(describeContractError("")).toBe("The contract rejected the transaction.");
    expect(describeContractError("x".repeat(500)).length).toBeLessThan(200);
  });
});
