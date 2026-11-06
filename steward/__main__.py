import argparse

from .pipeline import Steward


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask BI Steward a business question.")
    parser.add_argument("question", nargs="+")
    parser.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = parser.parse_args()

    result = Steward().ask(" ".join(args.question))
    if args.json:
        print(result.model_dump_json(indent=2))
        return

    decision = result.decision
    print(f"Verdict: {decision.verdict.value}")
    if decision.best:
        best = decision.best
        print(f"Report:  {best.artifact.id} — {best.artifact.title}")
        print(f"Coverage {best.coverage:.0%}, trust {best.trust:.2f}")
    print()
    print(result.explanation)


if __name__ == "__main__":
    main()
