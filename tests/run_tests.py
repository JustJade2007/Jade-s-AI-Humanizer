"""Script to run all unit tests and benchmarks programmatically."""

import sys
import pytest

if __name__ == "__main__":
    args = ["tests/unit", "tests/benchmarks", "-v"] + sys.argv[1:]
    exit_code = pytest.main(args)
    sys.exit(int(exit_code))
