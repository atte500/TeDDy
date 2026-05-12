def is_path_in_context_FIXED(path_str, context_files):
    if not path_str:
        return False
    
    def normalize(p):
        # 1. Standardize slashes
        # 2. Remove leading './' (common in relative paths)
        # 3. Remove leading '/'
        return p.replace("\\", "/").lstrip("./").lstrip("/")

    normalized_target = normalize(path_str)
    normalized_context = [normalize(p) for p in context_files]
    return normalized_target in normalized_context

def test_fix():
    test_cases = [
        ("README.md", ["README.md"]),
        ("README.md", ["\\README.md"]),
        ("README.md", [".\\README.md"]),
        ("\\README.md", ["README.md"]),
        ("src/logic.py", ["src\\logic.py"]),
    ]
    
    print("Verifying FIXED normalization logic:")
    all_passed = True
    for target, ctx in test_cases:
        result = is_path_in_context_FIXED(target, ctx)
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] Target: {target} | Context: {ctx} -> {result}")
        if not result:
            all_passed = False
            
    if all_passed:
        print("\nSUCCESS: All path variations correctly matched.")
    else:
        print("\nFAILURE: Some variations still mismatch.")

if __name__ == "__main__":
    test_fix()