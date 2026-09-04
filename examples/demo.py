"""What akashi does, what it cannot do, and what it says about both.

    python examples/demo.py

No arguments, no network, no model, no API key. Every number printed below is
computed when you run this; nothing here is a recorded transcript.
"""

from __future__ import annotations

from typing import Any

from akashi import evaluate, evaluate_samples

RULE = "-" * 78


def head(number: int, title: str) -> None:
    print(f"\n{RULE}\n {number}. {title}\n{RULE}")


def show(label: str, answer: str, contexts: list[str]) -> None:
    result = evaluate(answer=answer, contexts=contexts)
    share = "none" if result.grounded_share is None else f"{result.grounded_share:.2f}"
    print(f"\n  {label}")
    print(f"    answer   {answer}")
    for text in contexts:
        print(f"    evidence {text}")
    print(f"    -> share {share}   grounded {result.grounded}   floating {result.floating}")


def main() -> None:
    head(1, "The ordinary case: which strings the answer took from its evidence")
    show(
        "one figure quoted, one not",
        "The tent weighs 2.4kg and the gas is 9.9kg.",
        ["The tent weighs 2.4kg.", "Gas cartridge, 250mg."],
    )
    print("\n    9.9kg is `floating`: it is in none of the text that was sent.")
    print("    That is not the same as false, and akashi does not say that it is.")

    head(2, "Where akashi is WRONG, printed by akashi")
    show(
        "the value is real, the subject is not",
        "The tent weighs 2.4kg.",
        ["The stove weighs 2.4kg.", "The tent weighs 3.1kg."],
    )
    print("\n    A perfect score on a fabrication. A particular is a value with no")
    print("    subject, so nothing asks whether the sentence it was found in is about")
    print("    the same thing. That is issue #83, and it is first on the roadmap.")
    show("a correct paraphrase", "The tent weighs 2.4 kilograms.", ["Tent mass: 2.4kg."])
    print("\n    Zero on a correct answer. `--judge` is the answer to this one.")

    head(3, "Floating is not a dead end any more")
    result = evaluate(
        answer="The tent weighs 2.6kg.",
        contexts=["The tent weighs 3.1kg. The pack is 900g.", "Gas is 250mg."],
    )
    print("\n    answer   The tent weighs 2.6kg.")
    print(f"    -> floating {result.floating}")
    for near in result.nearby.values():
        print(f"       the evidence carries, of the same kind, near here: {', '.join(near)}")
    for segment in result.report.assessment.segments:
        for one in segment.particulars:
            for entry in one.nearby:
                span = entry.anchor.span
                print(f"         {entry.text:>7}  at {entry.item_id}[{span.start}:{span.end}]")
    print("\n    No similarity was computed and no ranking was applied. Scope is the")
    print("    only ordering. akashi is not saying you meant 3.1kg -- it is saying")
    print("    it read the evidence and this is what the evidence holds.")

    head(4, "What the limits say, on the artefact rather than in a README")
    for line in evaluate(answer="The tent weighs 2.4kg.", contexts=["x"]).limits:
        print(f"    - {line}")

    head(5, "A bound that changed the answer says so")
    digits = "1" * 301
    result = evaluate(answer=f"Transaction {digits} settled.", contexts=[f"Ref {digits}."])
    share = "none" if result.grounded_share is None else f"{result.grounded_share:.2f}"
    print(f"\n    a 301-digit identifier -> share {share}")
    print("    Nothing raised and nothing was slow. Until this week the report said")
    print("    only 'nothing to check'. Now it says which limit did it:\n")
    bounds: Any = result.to_dict()["bounds"]
    for bound in bounds:
        print(f"    {bound['name']}={bound['limit']}")
        print(f"      {bound['because']}")

    head(6, "A dataset, and an aggregate that refuses to be a bare number")
    rows: list[dict[str, Any]] = [
        {
            "user_input": "q",
            "response": "The tent weighs 2.4kg.",
            "retrieved_contexts": ["The tent weighs 2.4kg."],
        },
        {
            "input": "q",
            "actual_output": "A is 1.1kg, B is 2.2kg, C is 3.3kg, D is 4.4kg.",
            "retrieval_context": ["D is 4.4kg."],
        },
        {"question": "q", "answer": "It depends on the weather.", "contexts": ["Anything."]},
        {"question": "q", "answer": "No context at all.", "contexts": []},
    ]
    results = evaluate_samples(rows)
    print("\n    RAGAS + DeepEval + plain rows, mixed, in one call")
    print(f"    describe() -> {results.describe()}")
    print("\n    The mean of the row shares would be 0.625. The answer is 0.400,")
    print("    because the share counts particulars and not rows.")
    for refusal in results.refused:
        print(f"\n    row {refusal.index} was refused, not dropped:")
        print(f"      {refusal.reason[:96]}...")

    head(7, "In a test suite")
    from akashi.testing import GroundingError, assert_grounded

    try:
        assert_grounded(
            answer="The tent weighs 2.4kg and the gas is 9.9kg.",
            contexts=["The tent weighs 2.4kg."],
            at_least=0.9,
        )
    except GroundingError as failure:
        for line in str(failure).splitlines()[:9]:
            print(f"    {line}")
        print("    ...")

    print(f"\n{RULE}")
    print("  Next:")
    print("    akashi audit --contexts sample.json --json")
    print("    akashi audit --contexts sample.json --certificate report.html")
    print("    akashi doctor      what is installed, and what this console does to text")
    print("    akashi mcp         the same audit, for an agent rather than a person")
    print(RULE)


if __name__ == "__main__":
    main()
