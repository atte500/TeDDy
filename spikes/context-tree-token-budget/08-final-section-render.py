"""Renders the final compact tree section for this repository and a monorepo."""

import re
import tempfile
from pathlib import Path

import tiktoken

from teddy_executor.adapters.outbound.local_repo_tree_generator import (
    LocalRepoTreeGenerator,
)

ENCODER = tiktoken.get_encoding("cl100k_base")

SECTION_HEADER = re.compile(r"^\./(.+):$")
DEPTH_MARKER = re.compile(
    r"\[\.\.\. directory not expanded \(depth limit \d+\): ([^\]]+)\]"
)
UNREADABLE_MARKER = (
    "[... directory not expanded (unreadable): 0 folders, 0 files]"
)

DEPTH = 4
CAP = 30

SUBTITLES = {
    "named pair": (
        "*Tree capped at depth 4 and 30 entries per directory: "
        "deeper or wider directories show counts only.*"
    ),
    "threshold form": (
        "*Directories beyond depth 4 or 30 entries show child counts only.*"
    ),
    "compact form": "*Deeper than depth 4 or wider than 30 entries: counts only.*",
}


def tokens(text):
    return len(ENCODER.encode(text))


def render(depth, root="."):
    return LocalRepoTreeGenerator(root_dir=root, max_depth=depth).generate_tree()


def split_blocks(tree):
    """Splits a rendered tree into the root names and the section blocks."""
    root = []
    blocks = []
    current = None
    for line in tree.splitlines():
        header = SECTION_HEADER.match(line)
        if header:
            current = (header.group(1), [])
            blocks.append(current)
        elif line.strip():
            if current is None:
                root.append(line)
            else:
                current[1].append(line)
    return root, blocks


def is_marker(name):
    return name.startswith("[") and name.endswith("]")


def counts_text(folders, files):
    folder_noun = "folder" if folders == 1 else "folders"
    file_noun = "file" if files == 1 else "files"
    return f"{folders} {folder_noun}, {files} {file_noun}"


def apply_cap(tree, cap):
    """Collapses every directory above the cap and drops its descendants."""
    root, blocks = split_blocks(tree)
    keys = {path for path, _names in blocks}
    dropped = set()

    def counts_for(prefix, names):
        folders = 0
        for name in names:
            key = f"{prefix}/{name}" if prefix else name
            if key in keys:
                folders += 1
        return folders, len(names) - folders

    output = []
    if len(root) > cap:
        folders, files = counts_for("", root)
        output.append(f"[{counts_text(folders, files)}]")
    else:
        output.extend(root)

    for path, names in blocks:
        if any(path.startswith(prefix + "/") for prefix in dropped):
            continue
        output.append("")
        output.append(f"./{path}:")
        if len(names) == 1 and is_marker(names[0]):
            output.extend(names)
        elif len(names) > cap:
            dropped.add(path)
            folders, files = counts_for(path, names)
            output.append(f"[{counts_text(folders, files)}]")
        else:
            output.extend(names)
    return "\n".join(output).strip()


def compact_markers(tree):
    """Rewrites every long-form marker into its bare count form."""
    compacted = DEPTH_MARKER.sub(r"[\1]", tree)
    return compacted.replace(UNREADABLE_MARKER, "[unreadable]")


def section(tree, subtitle):
    return f"## Project Structure\n{subtitle}\n```\n{tree}\n```"


def build_monorepo(root):
    (root / ".gitignore").write_text("", encoding="utf-8")
    for name in ["README.md", "pyproject.toml", "Makefile", "uv.lock"]:
        (root / name).write_text("x", encoding="utf-8")

    docs = root / "docs"
    docs.mkdir()
    for index in range(12):
        (docs / f"guide-{index:02d}.md").write_text("x", encoding="utf-8")
    adr = docs / "adr"
    adr.mkdir()
    for index in range(30):
        (adr / f"{index:03d}-decision.md").write_text("x", encoding="utf-8")

    packages = root / "packages"
    packages.mkdir()
    for index in range(3):
        package = packages / f"pkg{index}"
        source = package / "src" / f"pkg{index}"
        source.mkdir(parents=True)
        (package / "pyproject.toml").write_text("x", encoding="utf-8")
        for name in ["__init__.py", "core.py", "models.py", "io.py", "cli.py"]:
            (source / name).write_text("x", encoding="utf-8")
        tests = package / "tests"
        tests.mkdir()
        for name in ["test_core.py", "test_models.py", "test_io.py"]:
            (tests / name).write_text("x", encoding="utf-8")

    captures = root / "assets" / "captures"
    captures.mkdir(parents=True)
    for index in range(50):
        (captures / f"shot-{index:03d}.png").write_text("x", encoding="utf-8")


def main():
    print("## Subtitle variants")
    print("| Variant | Text | Tokens |")
    print("| --- | --- | ---: |")
    for name, text in SUBTITLES.items():
        print(f"| {name} | {text} | {tokens(text)} |")

    tree = render(DEPTH)
    final_tree = compact_markers(apply_cap(tree, CAP))
    print()
    print("## Real repository token totals")
    print("| Variant | Tokens |")
    print("| --- | ---: |")
    print(f"| current long form | {tokens(tree)} |")
    print(f"| final section body | {tokens(final_tree)} |")

    print()
    print(f"## Real repository at depth {DEPTH}, cap {CAP}")
    print()
    print(section(final_tree, SUBTITLES["threshold form"]))

    with tempfile.TemporaryDirectory(prefix="big-tree-") as raw:
        root = Path(raw)
        build_monorepo(root)
        monorepo = compact_markers(apply_cap(render(DEPTH, str(root)), CAP))
        print()
        print(f"## Monorepo at depth {DEPTH}, cap {CAP}")
        print()
        print(section(monorepo, SUBTITLES["threshold form"]))


if __name__ == "__main__":
    main()