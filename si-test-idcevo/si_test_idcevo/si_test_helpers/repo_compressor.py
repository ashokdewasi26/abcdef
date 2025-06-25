import argparse
import subprocess
from pathlib import Path


def parse_arguments():
    arg_parser = argparse.ArgumentParser(description="Compressing of si-test-idcevo repository")

    arg_parser.add_argument(
        "--repo-path",
        type=Path,
        required=True,
        help="Repository path",
    )

    arg_parser.add_argument(
        "--with-data",
        action="store_true",
        required=False,
        help="Compress repository with si_test_data directory",
    )
    args = arg_parser.parse_args()
    return args


def main():
    args = parse_arguments()

    cmd = [
        "tar",
        "--exclude='.git'",
        "--exclude='.tox'",
    ]

    if not args.with_data:
        cmd.append("--exclude='si_test_data' ")

    cmd.append("-cvf si-test-idcevo.tar.gz si-test-idcevo/")
    subprocess.run(" ".join(cmd), cwd=args.repo_path, shell=True)


if __name__ == "__main__":
    main()
