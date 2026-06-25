"""
Modular prompt system (GSD-inspired context engineering).

Each module owns ONE concern. The base agent prompt stays short; detailed
instructions live in action descriptions or in the focused modules here.
This prevents "context rot" — the agent never holds 150 lines of mixed
instructions in its context at every step.

Modules:
    examly_base    — builds the concise base Examly prompt
    examly_coding  — the coding-question workflow (solve → verify → fix → move on)
    examly_mcq     — MCQ answering strategy
    examly_submit  — final submission gate + END typing
    troubleshooting — self-healing (modals, disabled buttons, etc.)
"""

from prompts.examly_base import build_examly_prompt
from prompts.examly_coding import CODING_WORKFLOW
from prompts.examly_mcq import MCQ_STRATEGY
from prompts.examly_submit import SUBMISSION_GATE
from prompts.troubleshooting import TROUBLESHOOTING

__all__ = [
    "build_examly_prompt",
    "CODING_WORKFLOW",
    "MCQ_STRATEGY",
    "SUBMISSION_GATE",
    "TROUBLESHOOTING",
]
