import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { CONTRACT_METHODS } from "./charterGate";

interface SchemaMethod {
  params: [string, unknown][];
  readonly?: boolean;
  payable?: boolean;
}
const schemaPath = fileURLToPath(new URL("../../../../docs/charter_gate.schema.json", import.meta.url));
const schema = JSON.parse(readFileSync(schemaPath, "utf-8")) as { methods: Record<string, SchemaMethod> };

describe("frontend wrapper matches the generated contract schema", () => {
  for (const [name, spec] of Object.entries(CONTRACT_METHODS)) {
    it(`${name}: exists, same arity, same read/write kind, not payable`, () => {
      const m = schema.methods[name];
      expect(m, `${name} missing from docs/charter_gate.schema.json`).toBeDefined();
      expect(m.params.length).toBe(spec.args);
      expect(Boolean(m.readonly)).toBe(!spec.write);
      expect(Boolean(m.payable)).toBe(false);
    });
  }
});
