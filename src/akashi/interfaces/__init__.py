"""The edges. The only place that knows which languages exist and where files are.

This is the composition root: it reads arguments, loads a package, chooses the
language packs, calls the use case and renders the result. Nothing above the
application layer decides anything about an answer.
"""
