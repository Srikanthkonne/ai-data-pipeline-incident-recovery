#!/usr/bin/env python3

import json
import subprocess
import sys
from pathlib import Path


TERRAFORM_DIR = Path(__file__).resolve().parent


def terraform_output():
    command = [
        "terraform",
        f"-chdir={TERRAFORM_DIR}",
        "output",
        "-json",
        "recovery_execution_environment",
    ]

    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )

    return json.loads(result.stdout)


def main():
    environment = terraform_output()

    for key in sorted(environment):
        print(f"{key}={environment[key]}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        raise SystemExit(exc.returncode)
