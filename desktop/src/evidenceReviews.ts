// A review belongs to exact source observations, not just a ticker/year label.
// Attached evidence is a snapshot so a reopened review retains its context.
export type Judgment = "unresolved" | "supported" | "contradicted";
export type EvidenceAttachment = { id: string; label: string; detail: string; url: string | null };
export type Hypothesis = {
  id: string; text: string; judgment: Judgment; note: string; evidence: EvidenceAttachment[];
};
export type EvidenceReview = { version: 1; trailId: string; hypotheses: Hypothesis[] };
type ReviewStorage = Pick<Storage, "getItem" | "setItem">;
const prefix = "fl:evidence-review:v1:";
const judgments = new Set(["unresolved", "supported", "contradicted"]);

export function readEvidenceReview(storage: ReviewStorage, trailId: string): EvidenceReview {
  const empty: EvidenceReview = { version: 1, trailId, hypotheses: [] };
  try {
    const value = JSON.parse(storage.getItem(prefix + trailId) || "null") as EvidenceReview | null;
    if (value?.version !== 1 || value.trailId !== trailId || !Array.isArray(value.hypotheses)) return empty;
    const valid = value.hypotheses.length <= 20 && value.hypotheses.every(item =>
      typeof item.id === "string" && typeof item.text === "string" && item.text.length <= 2000 &&
      typeof item.note === "string" && item.note.length <= 4000 && judgments.has(item.judgment) &&
      Array.isArray(item.evidence) && item.evidence.length <= 30 && item.evidence.every(source =>
        typeof source.id === "string" && typeof source.label === "string" &&
        typeof source.detail === "string" && (source.url === null || typeof source.url === "string")));
    return valid ? value : empty;
  } catch { return empty; }
}

export function saveEvidenceReview(storage: ReviewStorage, review: EvidenceReview): boolean {
  try { storage.setItem(prefix + review.trailId, JSON.stringify(review)); return true; }
  catch { return false; }
}
