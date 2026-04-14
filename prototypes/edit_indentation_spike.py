import textwrap

def get_indent(line: str) -> int:
    """Returns the number of leading spaces/tabs in a line."""
    return len(line) - len(line.lstrip())

def match_with_relative_indent(window_str: str, find_block: str) -> tuple[bool, int]:
    """
    Checks if window_str and find_block match with a constant indentation offset.
    Returns (matches, offset).
    """
    w_lines = [line.rstrip() for line in window_str.splitlines()]
    f_lines = [line.rstrip() for line in find_block.splitlines()]

    if len(w_lines) != len(f_lines):
        return False, 0

    offsets = []
    for w, f in zip(w_lines, f_lines):
        if not w.strip() and not f.strip():
            continue # Skip empty lines for offset calculation

        if w.strip() != f.strip():
            return False, 0

        offsets.append(get_indent(w) - get_indent(f))

    if not offsets:
        return False, 0

    # Check if all offsets are identical
    if len(set(offsets)) == 1:
        return True, offsets[0]

    return False, 0

def apply_indent_offset(replace_block: str, offset: int) -> str:
    """Applies the constant offset to every non-empty line in the replace_block."""
    lines = replace_block.splitlines(keepends=True)
    result = []
    for line in lines:
        if not line.strip():
            result.append(line)
        else:
            if offset > 0:
                result.append(" " * offset + line)
            elif offset < 0:
                # Remove spaces if possible, but don't strip code
                indent = get_indent(line)
                to_remove = min(abs(offset), indent)
                result.append(line[to_remove:])
            else:
                result.append(line)
    return "".join(result)

# --- Test Cases ---

def test_spike():
    # Case 1: Matching with 6-space relative indent (offset is +6 for all lines)
    find_1 = """  print("hello")
  if True:
      print("world")"""

    window_1 = """        print("hello")
        if True:
            print("world")"""

    replace_1 = """  print("hi")
  if False:
      print("nothing")"""

    print(f"Testing Case 1 (Constant Offset +6)...")
    matches, offset = match_with_relative_indent(window_1, find_1)
    print(f"  Matches: {matches}")
    print(f"  Offset: {offset}")

    if matches:
        final_replace = apply_indent_offset(replace_1, offset)
        print(f"  Final Replace Block:\n{textwrap.indent(final_replace, '  | ')}")

        expected_replace = """        print("hi")
        if False:
            print("nothing")"""
        assert final_replace.strip() == expected_replace.strip()
        print("  Case 1 Passed!")

    # Case 2: Matching with structural difference (offsets vary)
    find_2 = """  print("hello")
  if True:
    print("world")""" # 2 space relative

    print("\nTesting Case 2 (Varying Offsets)...")
    matches, _ = match_with_relative_indent(window_1, find_2)
    print(f"  Matches (should be False): {matches}")
    assert not matches
    print("  Case 2 Passed!")

    # Case 3: Negative offset (FIND is more indented than file)
    find_3 = "    print('hello')"
    window_3 = "  print('hello')"
    print("\nTesting Case 3 (Negative Offset -2)...")
    matches, offset = match_with_relative_indent(window_3, find_3)
    print(f"  Matches: {matches}")
    print(f"  Offset: {offset}")
    assert matches and offset == -2
    print("  Case 3 Passed!")

if __name__ == "__main__":
    test_spike()
