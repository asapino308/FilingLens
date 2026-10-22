import assert from "node:assert/strict";
import { test } from "node:test";
import { readEvidenceReview, saveEvidenceReview } from "../src/evidenceReviews.ts";

function storage() {
  const items = new Map();
  return { getItem: key => items.get(key) || null, setItem: (key, value) => items.set(key, value) };
}

test("judgments, notes and attached source snapshots survive reopening", () => {
  const saved = storage();
  const review = { version: 1, trailId: "source-version-1", hypotheses: [{
    id: "question-1", text: "Collections timing may be relevant", judgment: "unresolved", note: "Need more evidence",
    evidence: [{ id: "passage-1", label: "10-K filed 2025-02-01", detail: "The exact selected passage", url: "https://www.sec.gov/Archives/example.htm" }],
  }] };
  assert.equal(saveEvidenceReview(saved, review), true);
  assert.deepEqual(readEvidenceReview(saved, review.trailId), review);
  assert.deepEqual(readEvidenceReview(saved, "source-version-2").hypotheses, []);
});

test("corrupt or mismatched reviews do not leak into a different investigation", () => {
  const saved = storage();
  saved.setItem("fl:evidence-review:v1:a", "malformed");
  assert.deepEqual(readEvidenceReview(saved, "a").hypotheses, []);
  saved.setItem("fl:evidence-review:v1:a", JSON.stringify({ version: 1, trailId: "b", hypotheses: [] }));
  assert.equal(readEvidenceReview(saved, "a").trailId, "a");
  saved.setItem("fl:evidence-review:v1:a", JSON.stringify({ version: 1, trailId: "a", hypotheses: [{ judgment: "verified" }] }));
  assert.deepEqual(readEvidenceReview(saved, "a").hypotheses, []);
});

test("storage failure is reported so UI can preserve edits and offer export", () => {
  const denied = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("full"); } };
  assert.deepEqual(readEvidenceReview(denied, "a").hypotheses, []);
  assert.equal(saveEvidenceReview(denied, { version: 1, trailId: "a", hypotheses: [] }), false);
});
