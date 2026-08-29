"""The deterministic core.

Everything an audit decides is decided here, from values, with no I/O and no
imports outside the standard library (ADR-0001). No model runs in an audit at
all (ADR-0003), so there is nothing in this package that could ask one.
"""
