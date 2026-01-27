# Aksara ORM Benchmarks

Performance benchmark suite comparing Aksara against other async Python ORMs.

## Running Benchmarks

### Aksara Only

```bash
# Set database URL
export DATABASE_URL="postgresql://user:pass@localhost/aksara_bench"

# Run Aksara benchmarks
python aksara_bench.py
```

### All ORMs

```bash
# Install comparison ORMs (optional)
pip install sqlalchemy[asyncio] tortoise-orm piccolo

# Run all benchmarks
python run_all.py
```

## Benchmark Categories

### Single Record Operations
- **Create 100 records**: Sequential single inserts
- **Read 100 by ID**: Individual get() calls
- **Update 100 records**: Sequential save() calls

### Query Operations
- **Filter + Limit**: Filtered queries with limits
- **Complex query**: Multiple filters, ordering, limit
- **Count with filter**: COUNT operations

### Relation Performance (N+1 Prevention)
- **FK access NO preload**: N+1 pattern (baseline)
- **FK access WITH select_related**: Batched preloading
- **M2M access NO preload**: N+1 pattern (baseline)
- **M2M access WITH prefetch_related**: Batched preloading

## Understanding Results

The key metrics are:
- **Duration (ms)**: Lower is better
- **Ops/sec**: Higher is better
- **Query count**: For relation tests, fewer queries = better batching

### N+1 Prevention

The most important benchmarks show the difference between:

| Pattern | Queries | Performance |
|---------|---------|-------------|
| No preload (N+1) | 1 + N | Slow |
| select_related | 2 | Fast |
| prefetch_related (M2M) | 2 | Fast |

## Adding New Benchmarks

1. Create a new benchmark function in `aksara_bench.py`:

```python
async def bench_your_operation(db: Database) -> BenchmarkResult:
    async with async_timer() as timer:
        # Your benchmark code here
        pass
    
    return BenchmarkResult(
        name="Your Operation Name",
        duration_ms=timer.elapsed_ms,
        operations=100,  # Number of ops performed
    )
```

2. Add it to the `benchmarks` list in `run_benchmarks()`

## Implementing Comparison ORMs

The stub files (`sqlalchemy_bench.py`, etc.) contain TODO comments
showing how to implement equivalent benchmarks for other ORMs.
