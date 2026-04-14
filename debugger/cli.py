# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""
MCUB Debugger CLI - Command line interface.
"""

import argparse
import sys
from pathlib import Path

from debugger.types import DebugResult
from debugger.core import ModuleDebugger
from debugger import __version__


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcub-debugger",
        description="MCUB Module Debugger - Static analysis tool for MCUB modules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mcub-debugger module.py
  mcub-debugger modules/
  mcub-debugger modules/ -v
  mcub-debugger modules/ --output report.txt
  mcub-debugger modules/ --format json
        """,
    )

    parser.add_argument(
        "path",
        nargs="?",
        default="modules",
        help="Path to module file or modules directory (default: modules)",
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Quiet mode - only show issues"
    )

    parser.add_argument("-o", "--output", metavar="FILE", help="Save report to file")

    parser.add_argument(
        "-f",
        "--format",
        choices=["text", "json", "simple"],
        default="text",
        help="Output format (default: text)",
    )

    parser.add_argument(
        "--strict", action="store_true", help="Treat warnings as errors"
    )

    parser.add_argument(
        "--no-ast",
        action="store_true",
        help="Skip AST analysis (faster, less accurate)",
    )

    parser.add_argument(
        "--exclude", nargs="+", metavar="PATTERN", help="Exclude files matching pattern"
    )

    parser.add_argument(
        "--include",
        nargs="+",
        metavar="PATTERN",
        help="Only include files matching pattern",
    )

    parser.add_argument(
        "--version", action="version", version=f"mcub-debugger {__version__}"
    )

    return parser


def _get_colors() -> dict:
    if not sys.stdout.isatty():
        return {
            k: ""
            for k in [
                "red",
                "green",
                "yellow",
                "blue",
                "cyan",
                "white",
                "dim",
                "bold",
                "reset",
            ]
        }

    return {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "cyan": "\033[96m",
        "white": "\033[97m",
    }


def format_json(results: list[DebugResult]) -> str:
    """Format results as JSON."""
    import json

    output = {
        "version": __version__,
        "total_files": len(results),
        "files_with_issues": sum(1 for r in results if r.has_warnings or r.has_errors),
        "total_warnings": sum(len(r.warnings) for r in results),
        "total_errors": sum(len(r.errors) for r in results),
        "results": [],
    }

    for result in results:
        file_data = {
            "file": result.file_path,
            "module": result.module_name,
            "checked_lines": result.checked_lines,
            "duration_ms": result.duration_ms,
            "warnings": [
                {
                    "rule": w.rule_id,
                    "severity": w.severity,
                    "message": w.message,
                    "line": w.line,
                    "column": w.column,
                    "fix": w.fix_suggestion,
                }
                for w in result.warnings
            ],
            "errors": result.errors,
        }
        output["results"].append(file_data)

    return json.dumps(output, indent=2)


def format_simple(results: list[DebugResult]) -> str:
    """Format results as simple list."""
    lines = []

    for result in results:
        if result.is_clean:
            lines.append(f"OK {result.module_name}")
        else:
            lines.append(f"ISSUE {result.module_name}")
            for warning in result.warnings:
                lines.append(
                    f"  [{warning.rule_id}] {warning.message} ({result.file_path}:{warning.line})"
                )
            for error in result.errors:
                lines.append(f"  [ERROR] {error}")

    return "\n".join(lines)


def format_text(results: list[DebugResult], quiet: bool = False) -> str:
    """Format results as human-readable text."""
    colors = _get_colors()

    lines = []

    total_warnings = 0
    total_errors = 0

    for result in results:
        if result.is_clean:
            if not quiet:
                lines.append(
                    f"{colors['green']}OK{colors['reset']} {colors['white']}{result.module_name}{colors['reset']}"
                )
        else:
            lines.append(
                f"\n{colors['red']}ISSUE{colors['reset']} {colors['white']}{result.module_name}{colors['reset']} ({colors['dim']}{result.file_path}{colors['reset']})"
            )

            for warning in result.warnings:
                total_warnings += 1
                lines.append(warning.format())

            for error in result.errors:
                total_errors += 1
                lines.append(f"  {colors['red']}[ERROR]{colors['reset']} {error}")

            if not quiet:
                lines.append(
                    f"{colors['dim']}  Checked {result.checked_lines} lines in {result.duration_ms:.1f}ms{colors['reset']}"
                )

    summary = []
    if total_warnings > 0 or total_errors > 0:
        summary.append(f"\n{colors['yellow']}Summary:{colors['reset']}")
        if total_warnings > 0:
            summary.append(
                f"  {colors['yellow']}Warnings:{colors['reset']} {total_warnings}"
            )
        if total_errors > 0:
            summary.append(f"  {colors['red']}Errors:{colors['reset']} {total_errors}")
        summary.append(
            f"  {colors['dim']}Files checked:{colors['reset']} {len(results)}"
        )

    return "\n".join(lines + summary)


def main() -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    debugger = ModuleDebugger()
    path = Path(args.path)

    if not path.exists():
        print(f"Error: Path '{path}' does not exist", file=sys.stderr)
        return 1

    if path.is_file():
        results = [debugger.debug_file(path)]
    else:
        results = debugger.debug_directory(path)

    if not results:
        print("No Python files found to debug")
        return 0

    if args.format == "json":
        output = format_json(results)
    elif args.format == "simple":
        output = format_simple(results)
    else:
        output = format_text(results, args.quiet)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report saved to {args.output}")
    else:
        print(output)

    issues_found = any(r.has_warnings or r.has_errors for r in results)

    if args.strict and issues_found:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
