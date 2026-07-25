#!/usr/bin/env python3

import argparse
import hashlib
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_FORK_ROOT = Path("/sysroot/usr/src/rust")

CRATE_URL = "https://static.crates.io/crates/{crate}/{crate}-{version}.crate"

PATCH_SECTION = re.compile(r"^\[patch\.crates-io\]", re.MULTILINE)


def compatibility_series(version: str) -> str:
    parts = version.split(".")
    if parts[0] != "0":
        return parts[0]
    return ".".join(parts[:2])


@dataclass(frozen=True)
class Fork:
    directory: Path
    crate: str
    version: str

    @property
    def series(self) -> str:
        return compatibility_series(self.version)


def discover_forks(fork_root: Path) -> list[Fork]:
    forks = []

    for directory in sorted(fork_root.glob("rust-*")):
        if directory.name == "rust-src":
            continue

        manifest = directory / "Cargo.toml"
        if not manifest.is_file():
            continue

        with manifest.open("rb") as handle:
            package = tomllib.load(handle).get("package", {})

        if "name" in package and "version" in package:
            forks.append(Fork(directory, package["name"], str(package["version"])))

    return forks


def patch_table(forks: list[Fork], prefix: str) -> str:
    lines = ["[patch.crates-io]"]
    claimed: set[str] = set()

    for fork in forks:
        path = f"{prefix}/{fork.directory.name}"

        if fork.crate in claimed:
            key = fork.directory.name.removeprefix("rust-").replace("-", "_")
            lines.append(f'{key} = {{ package = "{fork.crate}", path = "{path}" }}')
        else:
            claimed.add(fork.crate)
            lines.append(f'{fork.crate} = {{ path = "{path}" }}')

    return "\n".join(lines) + "\n"


def lock_field(line: str, key: str) -> str | None:
    prefix = f'{key} = "'
    if line.startswith(prefix) and line.endswith('"'):
        return line[len(prefix) : -1]
    return None


def relock(lockfile: Path, forks: list[Fork]) -> bool:
    by_series = {(fork.crate, fork.series): fork for fork in forks}

    output: list[str] = []
    in_package = False
    name: str | None = None
    patched = False
    changed = False

    for line in lockfile.read_text().splitlines():
        if line.startswith("["):
            in_package = line.strip() == "[[package]]"
            name = None
            patched = False
        elif in_package:
            if (value := lock_field(line, "name")) is not None:
                name = value
            elif (value := lock_field(line, "version")) is not None:
                fork = by_series.get((name, compatibility_series(value)))
                if fork is not None:
                    patched = True
                    changed |= value != fork.version
                    output.append(f'version = "{fork.version}"')
                    continue
            elif patched and line.startswith(("source = ", "checksum = ")):
                changed = True
                continue

        output.append(line)

    if changed:
        lockfile.write_text("\n".join(output) + "\n")

    return changed


def patch_workspace(workspace: Path, forks: list[Fork], prefix: str) -> bool:
    manifest = workspace / "Cargo.toml"
    text = manifest.read_text()

    if PATCH_SECTION.search(text):
        return False

    manifest.write_text(text + "\n" + patch_table(forks, prefix))
    relock(workspace / "Cargo.lock", forks)
    return True


def cmd_patch_table(args: argparse.Namespace) -> None:
    forks = discover_forks(args.forks)
    prefix = args.prefix if args.prefix is not None else str(args.forks)
    sys.stdout.write(patch_table(forks, prefix))


def cmd_relock(args: argparse.Namespace) -> None:
    forks = discover_forks(args.forks)

    for lockfile in args.lockfile:
        if relock(lockfile, forks):
            print(f"* relocked {lockfile} onto the Zinnia crate forks")


def cmd_patch_workspace(args: argparse.Namespace) -> None:
    forks = discover_forks(args.forks)

    if patch_workspace(args.workspace, forks, args.prefix):
        print(f"* patched {args.workspace} onto the Zinnia crate forks")


def cmd_add_fork(args: argparse.Namespace) -> None:
    name = f"rust-{args.crate}"
    if args.suffix:
        name = f"{name}-{args.suffix}"

    recipe = ROOT / "recipes" / name
    if recipe.exists():
        sys.exit(f"rust-forks: {recipe} already exists")

    url = CRATE_URL.format(crate=args.crate, version=args.version)
    print(f"* fetching {url}...")
    with urllib.request.urlopen(url) as response:
        tarball = response.read()

    digest = hashlib.blake2b(tarball).hexdigest()
    print(f"* blake2b: {digest}")

    recipe.write_text(
        "#! /bin/sh\n"
        "\n"
        f"name={name}\n"
        f"version={args.version}\n"
        "revision=1\n"
        "\n"
        f"rust_crate_recipe {args.crate} \\\n"
        f"    {digest}\n"
    )
    print(f"* wrote recipes/{name}")

    register_fork(name)

    print(
        f"\nNext:\n"
        f"  cd build-<arch> && ../jinx/jinx build {name}   # fetch and apply patches\n"
        f"  $EDITOR sources/{name}-workdir/                # port the crate to Zinnia\n"
        f"  cd build-<arch> && ../jinx/jinx regen {name}   # write patches/{name}/\n"
    )


def register_fork(name: str) -> None:
    meta = ROOT / "recipes" / "rust-crates"
    text = meta.read_text()

    deps = re.search(r'^deps="([^"]*)"$', text, re.MULTILINE)
    revision = re.search(r"^revision=(\d+)$", text, re.MULTILINE)
    if deps is None or revision is None:
        sys.exit(f"rust-forks: cannot parse {meta}")

    if name in deps.group(1).split():
        print(f"* recipes/rust-crates already lists {name}")
        return

    text = text[: deps.start(1)] + f"{deps.group(1)} {name}" + text[deps.end(1) :]
    text = re.sub(
        r"^revision=\d+$",
        f"revision={int(revision.group(1)) + 1}",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    meta.write_text(text)
    print(f"* added {name} to recipes/rust-crates and bumped its revision")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="manage Zinnia's forks of crates.io crates"
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    def add_fork_root(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument(
            "--forks",
            type=Path,
            default=DEFAULT_FORK_ROOT,
            metavar="DIR",
            help="directory holding the rust-* crate forks",
        )

    table = subcommands.add_parser(
        "patch-table", help="print a [patch.crates-io] table for the installed forks"
    )
    add_fork_root(table)
    table.add_argument(
        "--prefix",
        metavar="PATH",
        help="path to write for each fork instead of its real location, "
        "for manifests that need a relative one",
    )
    table.set_defaults(handler=cmd_patch_table)

    lock = subcommands.add_parser(
        "relock", help="point a Cargo.lock at the forks so the patches apply"
    )
    add_fork_root(lock)
    lock.add_argument("lockfile", type=Path, nargs="+")
    lock.set_defaults(handler=cmd_relock)

    workspace = subcommands.add_parser(
        "patch-workspace", help="add the patch table to a workspace and relock it"
    )
    add_fork_root(workspace)
    workspace.add_argument("--prefix", metavar="PATH", required=True)
    workspace.add_argument("workspace", type=Path)
    workspace.set_defaults(handler=cmd_patch_workspace)

    fork = subcommands.add_parser(
        "add-fork", help="scaffold a fork of a crates.io crate"
    )
    fork.add_argument("crate")
    fork.add_argument("version")
    fork.add_argument(
        "--suffix",
        help="disambiguator for a crate forked at several incompatible versions",
    )
    fork.set_defaults(handler=cmd_add_fork)

    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
