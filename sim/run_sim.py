import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from sim.simulator import simulate_run

def main():
    parser = argparse.ArgumentParser(description="Run message metadata simulation.")
    parser.add_argument("--outdir", type=str, default="results/run01", help="Output directory")
    parser.add_argument("--num_users", type=int, default=10)
    parser.add_argument("--duration_s", type=int, default=60)
    parser.add_argument("--avg_msgs_per_min", type=int, default=10)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    simulate_run(
        outdir=args.outdir,
        num_users=args.num_users,
        duration_s=args.duration_s,
        avg_msgs_per_min=args.avg_msgs_per_min,
        seed=args.seed
    )

if __name__ == "__main__":
    main()
