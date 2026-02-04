# Question Bank Integration

## Priority Rule
1. Use question bank items that match the target KP + difficulty.
2. If insufficient, generate new items and mark as generated.

## Suggested Storage
- data/question_bank/questions.csv
- data/question_bank/stems/<id>.md
- data/question_bank/solutions/<id>.md

## questions.csv schema
- question_id
- kp_id
- difficulty (basic|medium|advanced)
- type (mcq|short|calc)
- stem_ref (path)
- answer_ref (path)
- source (book|lesson|exam|generated)
- tags (optional)

## Selection Strategy
- For each weak KP: 3-5 items
- Difficulty mix: 60% basic, 30% medium, 10% advanced
- Avoid repeating items used in last 2 weeks if possible
