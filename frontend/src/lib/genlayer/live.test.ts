import { createClient } from "genlayer-js";
import type { TransactionHash } from "genlayer-js/types";
import { describe, expect, it } from "vitest";
import { CHAIN } from "../../config/chain";
import type { TxState } from "./tx";
import { watchTransaction } from "./watch";

/**
 * OPT-IN live check against StudioNet. Skipped unless CHARTERGATE_LIVE=1, so the normal test run
 * never touches the network:
 *
 *   CHARTERGATE_LIVE=1 npx vitest run src/lib/genlayer/live.test.ts
 *
 * It sends no transactions. It reads already-finalized transactions from the Stage 1.1/1.2
 * verification deployments (hashes recorded in deployments/studionet.json) through the app's real
 * transaction layer.
 */
const live = process.env.CHARTERGATE_LIVE === "1";
const client = createClient({ chain: CHAIN });

async function outcome(hash: string): Promise<TxState> {
  return watchTransaction(
    hash as `0x${string}`,
    {
      getTransaction: (h) => client.getTransaction({ hash: h as TransactionHash }),
      sleep: (ms) => new Promise((r) => setTimeout(r, ms)),
    },
    () => undefined,
    { intervalMs: 200, maxPolls: 25 },
  );
}

describe.skipIf(!live)("live StudioNet: finality vs execution, through the real transaction layer", () => {
  const SUCCESS = {
    "Stage 1.2 add s1": "0x886e3c0a0aadda20d20a93940eae773d02a7c60605f2a7e29b8f7840301a2cea",
    "Stage 1.2 add s2": "0xeee6bc0f6cee6f9f07b8b38cac70742b4912c40b93ebda3c1dfd944d0d8a8dfe",
    "Stage 1.2 submit proposal": "0x905f73878759878728dee2221763211664f09569e79e776aea277b45cd975d56",
    "Stage 1.2 update s1": "0x40b196e5e613456045df7e1e123846c30fb5abcfb05ce17d383b17828ec7ab43",
    "Stage 1.2 deploy": "0x9e385374fd5ed11a933e086e61b87fa98715e29ccc7ce41b403a98c4faef6180",
  };
  const ROLLBACK = {
    "Stage 1.2 offset-bob NOT_OWNER": ["0xdb623df42cd7ee951284ab4ed78356afde31d1aa5c48322b1d115274d942cd5b", "EXPECTED:NOT_OWNER"],
    "Stage 1.2 integer section_id": ["0x16989973c853844b341b5438100376bc37491ca534179dc4b19a9e8b31747843", "EXPECTED:INVALID_TYPE:section_id"],
  } as const;

  for (const [label, hash] of Object.entries(SUCCESS)) {
    it(`${label}: FINALIZED + execution success => finalized`, async () => {
      const s = await outcome(hash);
      expect(s.networkStatus).toBe("FINALIZED");
      expect(s.execution).toEqual({ kind: "success" });
      expect(s.phase).toBe("finalized");
    }, 60_000);
  }

  for (const [label, [hash, code]] of Object.entries(ROLLBACK)) {
    it(`${label}: FINALIZED consensus but rolled back => failed (${code})`, async () => {
      const s = await outcome(hash);
      expect(s.networkStatus).toBe("FINALIZED"); // consensus finality is real...
      expect(s.phase).toBe("failed"); // ...but it is not a success
      expect(s.failure?.category).toBe("rolled_back");
      expect(s.failure?.code).toBe(code);
    }, 60_000);
  }

  it("Stage 1.1 raw TypeError transaction: FINALIZED but contract_error => failed, no stack trace in the message", async () => {
    const s = await outcome("0xe886a76b9fac3105ca8b43b49de9caa5242695271d83410bca7cf2af53305faa");
    expect(s.networkStatus).toBe("FINALIZED");
    expect(s.phase).toBe("failed");
    expect(s.failure?.category).toBe("contract_error");
    expect(s.failure?.message).not.toMatch(/Traceback/);
  }, 60_000);
});
