---
id: REQUEST-002
type: request
title: When the publisher publishes a work-item creating a PR in github, it currently
  m
workflow: analysis
step: submitted
---
When the publisher publishes a work-item creating a PR in github, it currently moves to 'done'. I want to be able to review the PR and either merge it or reject it with comments. Once I've merged or rejected, I would then move the work-item to either merged or rejected. For merged, the local main should be brought inline with origin. For rejected, the PR rejection comments should be read and passed back to implement.