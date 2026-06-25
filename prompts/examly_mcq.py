"""
examly_mcq.py — MCQ answering strategy prompt.

MCQ accuracy is already good, so this stays concise. Kept in its own module so
the base prompt doesn't mix concerns.
"""

MCQ_STRATEGY = """# MCQ QUESTIONS
- Read the full question and ALL options carefully.
- Eliminate obviously wrong options first.
- Select the best answer and confirm it's highlighted/selected.
- Save the question and your answer to the answer bank (discovery mode).
- Move to the next question."""
