## What does this PR do?

<!-- A brief description. Link any related issue (e.g. "Closes #12"). -->

## Type

- [ ] New system adapter (+ results)
- [ ] Data correction
- [ ] Bug fix
- [ ] Documentation
- [ ] Other

## Checklist

- [ ] The package imports and the free smoke checks pass:
      `pip install -e . && orgmembench list && orgmembench stats --tier small`
- [ ] I did **not** commit any API keys or credentials.
- [ ] For a new system: I included the adapter and the run results, and updated the leaderboard if
      appropriate.
- [ ] For a data correction: I referenced the question id(s) and the source-of-truth event/relation.
