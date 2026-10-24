# Track II · Part 7: Orchestrators, Schedules & SLAs

**Topic:** DAGs, retries, idempotent backfills  
**Status:** scaffold. The exercise lands here when this part's article is out.

## What's coming

A pipeline that runs on your laptop is only half the job; in production it has dependencies, retry policies, backfill windows, and a morning SLA. Part 7 walks through designing DAGs and idempotent backfills so a retry or replay never duplicates rows or misses a partition.

## Layout

- `starter/` will hold the exercise with `TODO`s for you to fill in.
- `solution/` will hold the finished version that passes the tests.

Both are empty for now. In the meantime, [Part 1](../part1/) is ready to run.
