"""akashi -- local-first response auditing for generative AI.

Take the answer a model gave you and the context it was given, and separate what
the answer took from its evidence from what it produced on its own. No model
runs inside an audit, so the same inputs give the same report forever.

The shortest way in, for somebody who has an answer and some strings:

```python
from akashi import evaluate

result = evaluate(
    answer="The tent weighs 2.4kg and the gas is 9.9kg.",
    contexts=["The tent weighs 2.4kg.", "Gas cartridge, 250mg."],
)
result.grounded_share   # 0.5
result.floating         # ('9.9kg',)
```

`evaluate_sample` takes a RAGAS or DeepEval sample dictionary unchanged.

**`grounded_share` is not a faithfulness score.** Every library in this space
reports a 0-1 number by that name, computed by asking a model whether the
context entails each claim. This one is the share of load-bearing strings in the
answer that occur in the text that was sent -- a different question, and
comparing the two numbers is comparing nothing. `result.limits` says so on the
object, and the report says so on the artefact.

See ``docs/adr/`` for the decisions behind it.
"""

from __future__ import annotations

from .errors import (
    AkashiError,
    ContractError,
    ProtectedResponseError,
    SegmentationError,
)
from .interfaces.api import (
    Refused,
    Result,
    Results,
    evaluate,
    evaluate_sample,
    evaluate_samples,
)
from .version import __version__

__all__ = [
    "AkashiError",
    "ContractError",
    "ProtectedResponseError",
    "Refused",
    "Result",
    "Results",
    "SegmentationError",
    "__version__",
    "evaluate",
    "evaluate_sample",
    "evaluate_samples",
]
