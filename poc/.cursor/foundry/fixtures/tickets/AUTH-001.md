---
id: AUTH-001
title: Refresh token rotation
type: Story
labels: [auth]
app: Example.Api
---

# AUTH-001 — Refresh token rotation

## Summary

Rotate refresh tokens on use so stolen tokens cannot be replayed indefinitely.

## Description

Identifier **AUTH-001** tracks local Foundry intake without Jira.

Implement refresh-token rotation for the API auth stack. On each successful refresh, invalidate the previous refresh token and issue a new one. Reject reuse of rotated tokens.

## Acceptance criteria

- [ ] Successful refresh returns a new refresh token and invalidates the previous one
- [ ] Reuse of a rotated refresh token is rejected
- [ ] Unit tests cover happy path and reuse rejection
