---
name: operator-onboarding-retro
description: >-
  Capture operator feedback as a product design investigation, grounded in the
  experienced commands and the code/docs behind them. Use for an onboarding or
  dogfooding retrospective; /evaluate-run owns run assessment.
---

# Operator onboarding retro

Follow [the operator-onboarding-retro skill](../skills/operator-onboarding-retro/SKILL.md).

Use the current conversation as the source of the operator's experience. Answer any immediate workflow question, then ask what the need for that answer reveals about the product. Trace material friction to implementation and documentation entrypoints. Explore design alternatives and tradeoffs for each feedback item.

If `run_path` is supplied, record its ID/path and the state relevant to the experience. Link an `/evaluate-run` output in the repository or chat; if none exists, write exactly **“evaluate-run not run—engine verdict omitted.”** Do not create a second run scorecard in the retro. Write or update the retro and its README entry. Do not commit unless requested.
