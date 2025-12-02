"""
Benchmark Runner

Runs all ORM benchmarks and produces a comparison report.

Usage:
    python run_all.py
"""

import asyncio
import json
import os
import sys
from datetime import datetime

# Add parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import print_comparison


def print_head_to_head(vidyut_suite, other_suite, other_name):
    """Print head-to-head comparison table."""
    print(f"\n{'=' * 75}")
    print(f"  Vidyut vs {other_name} - Head to Head")
    print(f"{'=' * 75}")
    print(f"{'Benchmark':<40} {'Vidyut':>12} {other_name:>12} {'Winner':>8}")
    print("-" * 75)
    
    vidyut_wins = 0
    other_wins = 0
    
    vidyut_results = {r.name: r for r in vidyut_suite.results}
    other_results = {r.name: r for r in other_suite.results}
    
    for name, vidyut_r in vidyut_results.items():
        other_r = other_results.get(name)
        if not other_r:
            continue
        
        v_ms = vidyut_r.duration_ms
        o_ms = other_r.duration_ms
        
        if v_ms < o_ms:
            winner = "Vidyut"
            speedup = o_ms / v_ms
            vidyut_wins += 1
        else:
            winner = other_name[:8]
            speedup = v_ms / o_ms
            other_wins += 1
        
        print(f"{name:<40} {v_ms:>10.2f}ms {o_ms:>10.2f}ms {winner:>8} ({speedup:.1f}x)")
    
    print("-" * 75)
    print(f"{'TOTAL WINS':<40} {vidyut_wins:>12} {other_wins:>12}")
    print(f"{'=' * 75}\n")


async def run_all():
    """Run all available benchmarks."""
    results = {}
    
    # Run Vidyut benchmarks
    try:
        from vidyut_bench import run_benchmarks as run_vidyut
        results["Vidyut"] = await run_vidyut()
    except Exception as e:
        print(f"Vidyut benchmark failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Run SQLAlchemy benchmarks
    try:
        from sqlalchemy_bench import run_benchmarks as run_sqla
        results["SQLAlchemy"] = await run_sqla()
    except ImportError as e:
        print(f"SQLAlchemy not installed: {e}")
    except Exception as e:
        print(f"SQLAlchemy benchmark failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Run Tortoise benchmarks
    try:
        from tortoise_bench import run_benchmarks as run_tortoise
        results["Tortoise"] = await run_tortoise()
    except ImportError as e:
        print(f"Tortoise not installed: {e}")
    except Exception as e:
        print(f"Tortoise benchmark failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Print head-to-head comparisons
    if "Vidyut" in results:
        if "SQLAlchemy" in results:
            print_head_to_head(results["Vidyut"], results["SQLAlchemy"], "SQLAlchemy")
        if "Tortoise" in results:
            print_head_to_head(results["Vidyut"], results["Tortoise"], "Tortoise")
    
    # Print summary table
    if len(results) > 1:
        print_summary_table(results)
    
    # Save to JSON
    if results:
        output = {
            "timestamp": datetime.now().isoformat(),
            "results": {
                name: suite.to_dict() 
                for name, suite in results.items()
            }
        }
        
        with open("benchmark_results.json", "w") as f:
            json.dump(output, f, indent=2)
        
        print("Results saved to benchmark_results.json")


def print_summary_table(results):
    """Print a summary comparison table of all ORMs."""
    print(f"\n{'=' * 90}")
    print("  Overall Comparison Summary")
    print(f"{'=' * 90}")
    
    # Get benchmark names from first result
    first_suite = list(results.values())[0]
    bench_names = [r.name for r in first_suite.results]
    
    # Header
    header = f"{'Benchmark':<40}"
    for orm_name in results.keys():
        header += f" {orm_name:>14}"
    print(header)
    print("-" * 90)
    
    # Results
    for bench_name in bench_names:
        row = f"{bench_name:<40}"
        times = {}
        for orm_name, suite in results.items():
            for r in suite.results:
                if r.name == bench_name:
                    times[orm_name] = r.duration_ms
                    row += f" {r.duration_ms:>12.2f}ms"
                    break
            else:
                row += " " * 14 + "N/A"
        print(row)
    
    print(f"{'=' * 90}\n")


if __name__ == "__main__":
    asyncio.run(run_all())
