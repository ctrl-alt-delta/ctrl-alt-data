# Track I · Part 2: Batches, Streams & Screams

**Topic:** Ingestion, batch vs streaming, ETL vs ELT  
**Status:** scaffold. The exercise lands here when this part's article is out.

## What's coming

Two decisions shape almost every pipeline. First, timing: load on a schedule in chunks (batch), or process events as they arrive (streaming). Second, order: transform the data on the way in (ETL) or land it raw and transform it inside the warehouse (ELT). Part 2 walks through both, what each choice costs, and why Part 1's freshness question settles more of it than people expect.

## Layout

- `starter/` will hold the exercise with `TODO`s for you to fill in.
- `solution/` will hold the finished version that passes the tests.

Both are empty for now. In the meantime, [Part 1](../week1/) is ready to run.
