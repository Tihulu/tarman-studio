from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __app_name__, __version__
from .core import (
    TarmanError,
    analyze_archive,
    install_archive,
    list_installed,
    uninstall,
)


def _print_analysis(analysis, json_output: bool = False) -> None:
    if json_output:
        print(json.dumps(analysis.as_dict(), indent=2))
        return
    print(f"Archive: {analysis.archive}")
    print(f"Name: {analysis.app_name}")
    print(f"Entries: {analysis.entries}")
    print(f"Top level: {analysis.top_level or '(multiple)'}")
    print(f"Recommended executable: {analysis.recommended_executable or '(none)'}")
    if analysis.executables:
        print("\nExecutables:")
        for item in analysis.executables:
            marker = " *" if item == analysis.recommended_executable else "  "
            print(f"{marker} {item}")
    if analysis.desktop_files:
        print("\nDesktop files:")
        for item in analysis.desktop_files:
            print(f"  {item}")
    if analysis.icons:
        print("\nIcons:")
        for item in analysis.icons[:10]:
            print(f"  {item}")
        if len(analysis.icons) > 10:
            print(f"  ... {len(analysis.icons) - 10} more")
    if analysis.install_scripts:
        print("\nInstall scripts found but not executed automatically:")
        for item in analysis.install_scripts:
            print(f"  {item}")
    if analysis.source_markers:
        print("\nSource/build markers:")
        for item in analysis.source_markers:
            print(f"  {item}")
    if analysis.warnings:
        print("\nWarnings:")
        for warning in analysis.warnings:
            print(f"  - {warning}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tarman",
        description="Install prebuilt portable Linux apps distributed as tar archives.",
    )
    parser.add_argument("--version", action="version", version=f"{__app_name__} {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="Inspect an archive and detect launchers.")
    p_analyze.add_argument("archive", type=Path)
    p_analyze.add_argument("--name", help="Display/application name override.")
    p_analyze.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    p_install = sub.add_parser("install", help="Install a prebuilt portable app tarball.")
    p_install.add_argument("archive", type=Path)
    p_install.add_argument("--name", help="Application name shown in app menus.")
    p_install.add_argument(
        "--executable",
        help="Launcher path inside the archive. Defaults to the detected recommended executable.",
    )
    p_install.add_argument(
        "--scope",
        choices=("user", "system"),
        default="user",
        help="Install to the user profile or /opt. System scope uses pkexec.",
    )
    p_install.add_argument("--destination", type=Path, help="Custom final installation directory.")
    p_install.add_argument("--no-desktop", action="store_true", help="Do not create a .desktop launcher.")
    p_install.add_argument("--overwrite", action="store_true", help="Replace an existing install directory.")
    p_install.add_argument("--terminal", action="store_true", help="Mark desktop launcher as terminal-based.")
    p_install.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    p_list = sub.add_parser("list", help="List apps installed by Tarman Studio.")
    p_list.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    p_uninstall = sub.add_parser("uninstall", help="Uninstall an app installed by Tarman Studio.")
    p_uninstall.add_argument("name", help="App name, slug, or manifest file name.")
    p_uninstall.add_argument("--keep-files", action="store_true", help="Remove manifest/launcher only, keep app files.")
    p_uninstall.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "analyze":
            analysis = analyze_archive(args.archive, app_name=args.name)
            _print_analysis(analysis, json_output=args.json)
            return 0
        if args.command == "install":
            result = install_archive(
                args.archive,
                app_name=args.name,
                executable=args.executable,
                scope=args.scope,
                destination=args.destination,
                create_desktop=not args.no_desktop,
                overwrite=args.overwrite,
                terminal=args.terminal,
            )
            if args.json:
                print(json.dumps(result.as_dict(), indent=2))
            else:
                print(f"Installed {result.app_name}")
                print(f"  Files: {result.install_dir}")
                print(f"  Launcher: {result.executable}")
                if result.desktop_file:
                    print(f"  Desktop entry: {result.desktop_file}")
                if result.used_privilege_escalation:
                    print("  Privilege escalation: pkexec")
            return 0
        if args.command == "list":
            installed = list_installed()
            if args.json:
                print(json.dumps(installed, indent=2))
            elif not installed:
                print("No apps installed by Tarman Studio.")
            else:
                for item in installed:
                    print(item.get("app_name", "Unknown"))
                    print(f"  Files: {item.get('install_dir')}")
                    print(f"  Launcher: {item.get('executable')}")
                    if item.get("desktop_file"):
                        print(f"  Desktop entry: {item.get('desktop_file')}")
            return 0
        if args.command == "uninstall":
            result = uninstall(args.name, keep_files=args.keep_files)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"Uninstalled {result['app_name']}")
                for path in result["removed"]:
                    print(f"  Removed: {path}")
            return 0
    except TarmanError as exc:
        print(f"tarman: error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
