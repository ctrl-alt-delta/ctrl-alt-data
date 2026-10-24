# Track II · Part 9: Compaction, Costs & Cold Sweat

**Topic:** Small-file problem, snapshot expiry  
**Status:** scaffold. The exercise lands here when this part's article is out.

## What's coming

Streaming and frequent micro-batches leave thousands of tiny Parquet files behind, slowing queries to a crawl and inflating storage bills. Part 9 shows how table maintenance—compaction, rewrite manifests, and snapshot expiry—keeps an Iceberg lakehouse fast and affordable.

## Layout

- `starter/` will hold the exercise with `TODO`s for you to fill in.
- `solution/` will hold the finished version that passes the tests.

Both are empty for now. In the meantime, [Part 1](../part1/) is ready to run.
