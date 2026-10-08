## Questions

1. When should the output pane be shown? (a) Always visible when the TUI opens until toggled with `l`, even while agents are stopped; (b) appears when an agent starts and collapses when idle, unless toggled off; (c) hidden until `l` is pressed. Should it take an even split of the right column with the detail view, or a smaller fixed height (say 6 rows)? On an 80x24 terminal an even split leaves the detail view about 5 usable lines.

   **Answer:** Output pane is closed by default. User toggles it to open when they want to see progress. It should take up the lower half of the detail section.
2. When an agent finishes or fails, should its last output stay on screen, labelled as finished or failed, until the next agent starts (recommended, so the customer can see what it was doing when it failed), or should the pane clear at once?

   **Answer:** The output should stay on the screen. It should not have any additional information added, it is just a stream from the agent.
3. The project check step (running the test suite) shows "running" in the tree but streams no output. Should the pane (a) stay idle for check steps, with header wording that does not claim nothing is running, or (b) show a header naming the check while it runs, with no lines streamed? Streaming check output would be a separate story.

   **Answer:** The output pane is just what is coming out of agent interactions so the check step is not relevant.
4. When the next agent starts, should the pane be emptied first, or should output simply keep scrolling as one continuous stream (like `tail -f`, bounded to the last 2000 lines, with runs told apart by the "started" lines in the activity log)? Emptying means that when one agent fails and another item is pending, the failed run's output disappears as soon as the next agent starts, usually within seconds. My recommendation is a continuous stream: it is simpler and keeps failure output on screen.

   **Answer:** It should keep the existing output, just adding the output from the next agent to what is already there

