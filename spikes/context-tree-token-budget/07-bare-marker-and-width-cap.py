"""Prices the compact marker set and a per-directory width cap."""

import re

import tiktoken

from teddy_executor.adapters.outbound.local_repo_tree_generator import (
    LocalRepoTreeGenerator,
)

ENCODER = tiktoken.get_encoding("cl100k_base")

SECTION_HEADER = re.compile(r"^\./(.+):$")

DEPTHS = [3, 4, 5, 6, 7]
CAPS = [None, 50, 30, 20]
SENTINEL = "test_walking_skeleton.py"

PLAIN_SUBTITLE = "*Deeper or wider directories show counts only.*"
NUMBERED_SUBTITLE = (
    "*Tree capped at depth {depth} and {cap} entries per directory: "
    "deeper or wider directories show counts only.*"
)

RENDER_DEPTH = 5
RENDER_CAP = 30


def tokens(text):
    return len(ENCODER.encode(text))


def render(depth):
    return LocalRepoTreeGenerator(root_dir=".", max_depth=depth).generate_tree()


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


def apply_cap(tree, cap, cap_root=True):
    """Collapses every directory above the cap and drops its descendants."""
    root, blocks = split_blocks(tree)
    keys = {path for path, _names in blocks}
    dropped = set()
    collapsed = 0

    def counts_for(prefix, names):
        folders = 0
        for name in names:
            key = f"{prefix}/{name}" if prefix else name
            if key in keys:
                folders += 1
        return folders, len(names) - folders

    output = []
    if cap is not None and cap_root and len(root) > cap:
        folders, files = counts_for("", root)
        output.append(f"[{counts_text(folders, files)}]")
        collapsed += 1
    else:
        output.extend(root)

    for path, names in blocks:
        if any(path.startswith(prefix + "/") for prefix in dropped):
            continue
        output.append("")
        output.append(f"./{path}:")
        if len(names) == 1 and is_marker(names[0]):
            output.extend(names)
        elif cap is not None and len(names) > cap:
            dropped.add(path)
            folders, files = counts_for(path, names)
            output.append(f"[{counts_text(folders, files)}]")
            collapsed += 1
        else:
            output.extend(names)

    return "\n".join(output).strip(), collapsed


def marker_variants():
    counts = "2 folders, 0 files"
    variants = {
        "bare counts": f"[{counts}]",
        "ellipsis prefix": f"[... {counts}]",
        "omitted suffix": f"[{counts} omitted]",
        "unreadable": "[unreadable]",
        "current long form": (
            f"[... directory not expanded (depth limit 4): {counts}]"
        ),
    }
    print("## Marker cost, one line")
    print("| Variant | Example | Tokens |")
    print("| --- | --- | ---: |")
    for name, text in variants.items():
        print(f"| {name} | `{text}` | {tokens(text)} |")


def width_distribution(depth):
    _root, blocks = split_blocks(render(depth))
    widths = sorted(
        (
            (len(names), path)
            for path, names in blocks
            if not any(map(is_marker, names))
        ),
        reverse=True,
    )
    print()
    print(f"## Widest sections at depth {depth}")
    print("| Entries | Section |")
    print("| ---: | --- |")
    for width, path in widths[:12]:
        print(f"| {width} | `./{path}` |")


def ladder():
    print()
    print("## Depth and width ladder, bare markers, root capped")
    print("| Depth | Cap | Long form | Shaped | Saved | Collapsed | Sentinel |")
    print("| ---: | ---: | ---: | ---: | ---: | ---: | :--- |")
    for depth in DEPTHS:
        tree = render(depth)
        long_form = tokens(tree)
        for cap in CAPS:
            shaped, collapsed = apply_cap(tree, cap)
            marker_lines = sum(1 for line in shaped.splitlines() if is_marker(line))
            cap_label = "none" if cap is None else str(cap)
            visible = "yes" if SENTINEL in shaped else "no"
            print(
                f"| {depth} | {cap_label} | {long_form} | {tokens(shaped)} "
                f"| {long_form - tokens(shaped)} | {collapsed} | {visible} |"
            )


def root_sensitivity():
    tree = render(5)
    root, _blocks = split_blocks(tree)
    capped, _collapsed = apply_cap(tree, 30, cap_root=True)
    kept, _collapsed = apply_cap(tree, 30, cap_root=False)
    print()
    print(f"## Root has {len(root)} entries at depth 5")
    print(f"- root capped: {tokens(capped)} tokens")
    print(f"- root kept: {tokens(kept)} tokens")


def subtitle_cost():
    print()
    print("## Subtitle cost")
    print(f"- plain: {tokens(PLAIN_SUBTITLE)} tokens")
    print(
        f"- numbered: {tokens(NUMBERED_SUBTITLE.format(depth=RENDER_DEPTH, cap=RENDER_CAP))} tokens"
    )


def final_render():
    shaped, _collapsed = apply_cap(render(RENDER_DEPTH), RENDER_CAP)
    print()
    print(f"## Proposed section at depth {RENDER_DEPTH}, cap {RENDER_CAP}")
    print()
    print("## Project Structure")
    print(NUMBERED_SUBTITLE.format(depth=RENDER_DEPTH, cap=RENDER_CAP))
    print("```")
    print(shaped)
    print("```")


DEPTH_MARKER = re.compile(
    r"\[\.\.\. directory not expanded \(depth limit \d+\): ([^\]]+)\]"
)

UNREADABLE_MARKER = (
    "[... directory not expanded (unreadable): 0 folders, 0 files]"
)


def compact_markers(tree):
    """Rewrites every long-form marker into its bare count form."""
    compacted = DEPTH_MARKER.sub(r"[\1]", tree)
    return compacted.replace(UNREADABLE_MARKER, "[unreadable]")


def packaging_ladder():
    """Reports the full package: a width cap plus bare markers everywhere."""
    print()
    print("## Full package: width cap plus bare markers on every line")
    print("| Depth | Cap | Long form | Packaged | Saved | Markers |")
    print("| ---: | ---: | ---: | ---: | ---: | ---: |")
    for depth in DEPTHS:
        tree = render(depth)
        long_form = tokens(tree)
        for cap in CAPS:
            shaped, _collapsed = apply_cap(tree, cap)
            packaged = compact_markers(shaped)
            markers = sum(1 for line in packaged.splitlines() if is_marker(line))
            cap_label = "none" if cap is None else str(cap)
            print(
                f"| {depth} | {cap_label} | {long_form} | {tokens(packaged)} "
                f"| {long_form - tokens(packaged)} | {markers} |"
            )


if __name__ == "__main__":
    import sys

    marker_variants()
    width_distribution(5)
    ladder()
    packaging_ladder()
    root_sensitivity()
    subtitle_cost()
    if "render" in sys.argv[1:]:
        final_render()