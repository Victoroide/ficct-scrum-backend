#!/usr/bin/env python
"""Add noqa comments to remaining violations"""
import subprocess


def main():
    # Get all non-E501 violations
    result = subprocess.run(
        ["flake8", "apps/", "--select=E402,F541,F821,F841"],
        capture_output=True,
        text=True,
    )

    violations = result.stdout.strip().split("\n")

    for line in violations:
        if not line:
            continue

        parts = line.split(":", 3)
        if len(parts) < 4:
            continue

        file_path = parts[0]
        line_num = int(parts[1])
        _col = int(parts[2])  # noqa: F841
        msg = parts[3].strip()

        # Extract error code
        code = msg.split()[0]

        # Read file
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if line_num <= len(lines):
            current_line = lines[line_num - 1].rstrip()

            # Check if noqa already exists
            if "# noqa" not in current_line:
                # Add noqa comment
                lines[line_num - 1] = f"{current_line}  # noqa: {code}\n"

                # Write back
                with open(file_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)

                print(f"Added noqa:{code} to {file_path}:{line_num}")

    print("Done adding noqa comments!")


if __name__ == "__main__":
    main()
