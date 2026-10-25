Analyse this work item against the repository you are in. Do not change any
files other than the work item.

Establish whether the item is understood well enough to implement: what exists
today, what would change, and whether its acceptance criteria are concrete and
checkable. Record your findings in the item body, and add or tighten the
acceptance criteria there.

If you cannot proceed without an answer from the customer, add each question as
an item in a numbered list under a `## Questions` heading in the item body and
choose `questions`. The customer's reply appears beneath each question as
`**Answer:** ...`. Leave earlier questions and their answers in place and add
new questions to the end of the list. Assumptions you are comfortable
stating are not questions. Otherwise choose `analysed`; the item then goes to a
challenger before the customer sees it.

If the item has a `## Challenge` section, it was sent back to you. Address each
finding in the item, by changing it or by asking the customer, before choosing
`analysed` again.

Do not write an `**Answer:**` line under a new question; the customer's reply
is added beneath it. Keep one `## Questions` heading and one numbered list
across rounds, with no nested lists, and put findings elsewhere.

Record dependencies when this work needs code from another story, task or bug
before implementation can start. Use `{{harness_command}} backlog depends-on
<item-id> <dependency-id> ...` to replace the list, or omit dependency IDs to
clear it. A valid `depends_on` change is permitted during analysis; keep other
front-matter fields unchanged. Do not use epics or requests as dependencies.
Dependencies must reach `done` before the first branch role starts. An
`abandoned` dependency blocks unbranched work until the customer edits the
list. Once the item's branch exists, dependencies no longer hold it.
