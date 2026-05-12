def is_path_in_context_fixed(
    path_str: str,
    context_paths: dict,
    check_session: bool = True,
    check_turn: bool = True,
) -> bool:
    """FIXED: Normalizes both target and context paths to use forward slashes."""
    if not context_paths or not path_str:
        return False

    scopes = []
    if check_session:
        scopes.append("Session")
    if check_turn:
        scopes.append("Turn")

    # Normalize target: remove leading slash AND convert backslashes
    normalized_target = path_str.lstrip("/").replace("\\", "/")

    for scope in scopes:
        context_files = context_paths.get(scope, [])
        # Normalize context: remove leading slash AND convert backslashes
        normalized_context = [p.lstrip("/").replace("\\", "/") for p in context_files]
        if normalized_target in normalized_context:
            return True

    return False

def test_verification():
    # Simulate Windows resolved context paths (backslashes)
    context_paths = {
        "Turn": ["src\\logic.py", "README.md"]
    }
    
    # Target path from a TeDDy plan (always forward slashes)
    target = "src/logic.py"
    
    print(f"Checking if '{target}' is in context (FIXED logic)...")
    result = is_path_in_context_fixed(target, context_paths)
    
    print(f"Result: {result}")
    
    if result is True:
        print("SUCCESS: Path found (Fix verified).")
        exit(0)
    else:
        print("FAILURE: Fix failed to normalize paths.")
        exit(1)

if __name__ == "__main__":
    test_verification()