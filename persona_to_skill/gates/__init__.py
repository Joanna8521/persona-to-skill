# -*- coding: utf-8 -*-
"""Gates. Each returns a Verdict; a non-passing Verdict blocks delivery.

Every gate here is built to three rules, taken from the house rules on gates
with teeth:
  1. recompute independently: never confirm a value using the method that
     produced it;
  2. fail closed: when the input a check depends on is absent, block, do not
     wave through;
  3. check the artifact actually being delivered, not a fixture, not the
     previous run.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Verdict:
    gate: str
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.passed
