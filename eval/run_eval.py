import os
import sys
import json

_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from src.rag_retriever import hybrid_match


def run_evaluation(test_file: str = None) -> dict:
    if test_file is None:
        test_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "test_queries.json"
        )

    with open(test_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    test_cases = data["test_cases"]
    results = []
    top1_hits = 0
    top3_hits = 0
    acceptable_hits = 0
    score_errors = 0

    print("=" * 72)
    print("  ACADEMIMATCH — EVALUATION HARNESS")
    print("=" * 72)
    print(f"Test cases: {len(test_cases)}")
    print("-" * 72)

    for i, tc in enumerate(test_cases, 1):
        query = tc["query"]
        expected_top1 = tc["expected_top1"]
        acceptable_top3 = set(tc["acceptable_top3"])
        description = tc.get("description", "")

        retrieved = hybrid_match(query, top_k=3)

        if not retrieved:
            print(f"[FAIL] {i}. \"{query}\" — no results")
            results.append({"query": query, "result": "no_results", "passed": False})
            continue

        result_ids = [r["id"] for r in retrieved]
        actual_top1 = result_ids[0] if result_ids else None
        scores = [r.get("hybrid_pct", 0) for r in retrieved]

        top1_ok = actual_top1 == expected_top1
        top3_ok = expected_top1 in result_ids[:3]
        acceptable_ok = all(rid in acceptable_top3 for rid in result_ids[:3])

        if not top1_ok and actual_top1 in acceptable_top3:
            pass

        if top1_ok:
            top1_hits += 1
        if top3_ok:
            top3_hits += 1
        if acceptable_ok:
            acceptable_hits += 1

        status = "PASS" if top1_ok else ("OK-TOP3" if top3_ok else "FAIL")
        results.append({
            "query": query,
            "expected_top1": expected_top1,
            "actual_top1": actual_top1,
            "top1_match": top1_ok,
            "top3_match": top3_ok,
            "result_ids": result_ids,
            "scores": scores,
            "passed": top1_ok or top3_ok,
        })

        print(f"[{status}] {i:2d}. \"{query[:50]}{'...' if len(query)>50 else ''}\"")
        print(f"      Expected #1: {expected_top1} -> Got #1: {actual_top1}")
        if retrieved:
            print(f"      Top 3: {[f'{r['name']} ({r['hybrid_pct']}%)' for r in retrieved[:3]]}")
        print()

    total = len(test_cases)
    top1_acc = top1_hits / total * 100
    top3_recall = top3_hits / total * 100
    acc_cov = acceptable_hits / total * 100

    print("-" * 72)
    print(f"RESULTS SUMMARY:")
    print(f"  Top-1 Accuracy:     {top1_hits}/{total} ({top1_acc:.1f}%)")
    print(f"  Top-3 Recall:       {top3_hits}/{total} ({top3_recall:.1f}%)")
    print(f"  Acceptable Coverage: {acceptable_hits}/{total} ({acc_cov:.1f}%)")
    print("=" * 72)

    return {
        "total": total,
        "top1_accuracy": top1_acc,
        "top3_recall": top3_recall,
        "acceptable_coverage": acc_cov,
        "results": results,
    }


if __name__ == "__main__":
    run_evaluation()
