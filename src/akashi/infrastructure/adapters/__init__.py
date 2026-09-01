"""The one layer allowed to know a sibling exists.

`.importlinter`'s `the-redactor-is-optional` contract forbids `mamori` to the
domain, the ports, the application, the evaluation and the interfaces. This
package is what is left, and it is where a seam to somebody else's library goes
if it goes anywhere.

Today it holds one, and that one imports nothing (see `mamori`). The contract
still names this package rather than excluding it, so that a second adapter
arrives already governed rather than being noticed afterwards.
"""

from __future__ import annotations

from .mamori import MamoriRestorer, RestoresText

__all__ = ["MamoriRestorer", "RestoresText"]
