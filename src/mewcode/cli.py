"""MewCode CLI interface"""

import argparse
import sys


def cli():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        prog="mewcode",
        description="MewCode - A terminal AI coding assistant",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="LLM model to use (e.g., gpt-4, claude-3-5-sonnet)",
    )

    parser.add_argument(
        "--provider",
        "-p",
        type=str,
        default=None,
        choices=["openai", "claude", "ollama", "custom"],
        help="LLM provider",
    )

    args = parser.parse_args()

    # Import and run TUI
    from mewcode.tui.app import run_app
    run_app(model=args.model, provider=args.provider)
