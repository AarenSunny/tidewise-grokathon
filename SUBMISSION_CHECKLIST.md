# 4:45 PM submission checklist

Use this as a rapid final handoff. Assign one person to own the clock and one person to independently open every public link in an incognito window.

## Must be complete before 4:45 PM

- [ ] **Public GitHub repository:** default branch contains the working app, README, license/attribution, and no secrets or personal data.
- [ ] **Grok Bot session export:** included in the repository or clearly linked, with personal information removed.
- [ ] **Live-data proof:** demo visibly shows current timestamps, named public sources, and at least one recommendation derived from real data.
- [ ] **Depth proof:** README/demo explains normalization, multi-source logic, activity scoring, safety gates, confidence, and provenance—not only API display.
- [ ] **Robustness proof:** demonstrate or explain missing values, stale data, upstream errors, fallback/last-known-good behavior, and an honest unavailable state.
- [ ] **Run instructions:** exact prerequisites, environment setup, install, start, and test commands work from a fresh clone.
- [ ] **Deployment or local fallback:** public deployment works; otherwise the local demo path is rehearsed and fully documented.
- [ ] **Video:** public link, two minutes or less, audio/text readable, no private tabs, tokens, notifications, or personal data visible.
- [ ] **Slides:** public presentation/slideshow link opens without login.
- [ ] **Submission form:** repository, video, slides, deployment (if any), team details, and required answers are entered and reviewed.

## Suggested two-minute video cut

- [ ] `0:00–0:15` — problem, target user, and activity choice.
- [ ] `0:15–0:55` — live recommendation: location, time, score/confidence, explanation, and source timestamps.
- [ ] `0:55–1:20` — data pipeline and activity-specific processing.
- [ ] `1:20–1:40` — failure/stale-data behavior and safety disclaimer.
- [ ] `1:40–1:55` — why this helps someone on the ground and how Grok Bot contributed.
- [ ] `1:55–2:00` — project name and public repository URL.

## Final 15-minute sequence

- [ ] Freeze feature work; only fix submission-blocking defects.
- [ ] Run automated tests and one clean-clone/local-start smoke test.
- [ ] Load a real recommendation and confirm the source timestamps are current.
- [ ] Check responsive/demo viewport and prepare one known-good location/activity.
- [ ] Scan tracked files and commit history for `.env`, tokens, email addresses, local paths, and raw session exports.
- [ ] Open repository, video, slides, and deployment links in an incognito window.
- [ ] Submit by **4:45 PM**; save confirmation evidence.

## Fast repository checks

```bash
git status --short
git ls-files
git log -1 --oneline
```

Add the selected stack's test, build, lint, and clean-start commands here before handoff.

