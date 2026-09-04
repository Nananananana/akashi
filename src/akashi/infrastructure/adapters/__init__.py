"""The one layer allowed to know a sibling exists.

`.importlinter`'s `the-redactor-is-optional` contract forbids `mamori` to the
domain, the ports, the application, the evaluation and the interfaces. This
package is what is left, and it is where a seam to somebody else's library goes
if it goes anywhere.

Two live here now, and they are the two ends of what this layer is for.

`mamori` imports nothing: the seam is a shape, and akashi installs and runs
without the library.

`claude_judge` is the other end -- the first thing in akashi that **reaches the
network**, behind an extra and behind an explicit `--judge`. Everything below
this layer stays offline and stdlib-only, and the import-linter contract is what
holds that rather than a convention. The SDK is imported inside a function, so a
machine without the extra gets a message about what to install rather than an
ImportError from `import akashi`.
"""

from __future__ import annotations

from .mamori import MamoriRestorer, RestoresText

#: `claude_judge` is **not** re-exported here on purpose. Importing this package
#: would then import the SDK, and `import akashi` would reach the network stack
#: on any machine with the extra installed. A caller who wants a judge imports
#: `akashi.infrastructure.adapters.claude_judge` and pays for it deliberately;
#: the import-linter contract is what caught this being otherwise.
__all__ = ["MamoriRestorer", "RestoresText"]
