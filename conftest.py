"""Repo-wide pytest options.

    python -m pytest part1                    tests the reference solution
    python -m pytest part1 --target starter   tests your code in part1/starter/
"""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--target",
        action="store",
        default="solution",
        choices=("solution", "starter"),
        help="which implementation to test: solution (default) or starter",
    )


@pytest.fixture(scope="session")
def target_name(request) -> str:
    return request.config.getoption("--target")
