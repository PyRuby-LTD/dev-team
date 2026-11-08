The customer has accepted this {{ item.type }} for publishing, and bringing its
branch up to date with {{ base }} before the pull request stopped at conflicts.
Resolve them as you would before review: the change being published is the one
the customer accepted, so keep its behaviour exactly and take nothing more from
{{ base }} than the merge needs.

{% include "resolve.md" %}
