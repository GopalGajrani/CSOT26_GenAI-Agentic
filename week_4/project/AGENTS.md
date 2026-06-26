# Code Scout Rules

## Tools
- Prefer run_command for git history, tests, and broad search (grep/find)
- Use read_file once you know the file and roughly which lines matter
- Prefer edit_file over run_command for precise, line-level changes;
  use run_command for anything edit_file doesn't cover
- Expect destructive or unclassified commands and any write/edit to pause
  for human approval — that's normal, not an error

## Planning
- For any task with more than one sub-question, call todo_write first with
  your full plan before doing anything else
- Update todo_write as items complete — don't batch updates to the end
- A todo item that changes code is not "completed" until the relevant
  verification command (usually the test suite) has actually exited 0 —
  cite the exit code as evidence

## Citations
- Always cite file:line for any claim about behavior
- If grep/run_command returns zero results, try a broader term before
  reporting that something doesn't exist