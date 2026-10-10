import type { Tone } from "../components/primitives";
import type { PrecedentCandidate, PrecedentCitation, PrecedentTreatment, ReviewPrecedents } from "./genlayer/charterGate";

/**
 * Presentation rules for precedent memory. Nothing here decides anything: the candidates, the citations and every hash are
 * read from the contract. Precedent is advisory: it never outranks the charter or the current evidence.
 */

export const ADVISORY_NOTE = "Prior rulings guide consistency but do not override the charter or current evidence.";
export const NO_PRECEDENT = "No prior rulings available for this rule.";

export const TREATMENT_INFO: Record<PrecedentTreatment, { label: string; tone: Tone; explain: string }> = {
  FOLLOWED: {
    label: "FOLLOWED",
    tone: "eligible",
    explain: "The prior ruling was materially relevant and this finding is consistent with it.",
  },
  DISTINGUISHED: {
    label: "DISTINGUISHED",
    tone: "warning",
    explain: "The prior ruling was relevant, but a material difference in this case justifies a different treatment.",
  },
};

export interface SectionPrecedent {
  sectionId: string;
  /** The rule identity shared with the prior rulings ("" when there were none). */
  rule: string;
  candidates: PrecedentCandidate[];
  citations: PrecedentCitation[];
}

/** Groups a review's snapshot and citations by constitutional section, in the order the sections were reviewed. */
export function precedentBySection(precedents: ReviewPrecedents, sectionIds: readonly string[]): SectionPrecedent[] {
  return sectionIds.map((sectionId) => {
    const candidates = precedents.candidates.filter((c) => c.section_id === sectionId);
    return {
      sectionId,
      rule: candidates[0]?.rule ?? "",
      candidates,
      citations: precedents.citations.filter((c) => c.section_id === sectionId),
    };
  });
}

/** "s3@4" -> "§s3 · revision 4". The rule identity is the section AND the exact revision that governed the finding. */
export function describeRule(rule: string): string {
  const m = /^(.+)@(\d+)$/.exec(rule);
  return m ? `§${m[1]} · revision ${m[2]}` : rule;
}

export const hasPrecedent = (p: ReviewPrecedents) => p.candidates.length > 0;
