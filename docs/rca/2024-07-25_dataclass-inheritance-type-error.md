# RCA: TypeError: non-default argument follows default argument

## 1. Summary
The system experienced a `TypeError: non-default argument 'command' follows default argument` during test collection. This occurred because the `ExecuteAction` dataclass, which defines a required field (`command`), inherited from the `Action` dataclass, which defined a field with a default value (`params`). This created an invalid `__init__` method signature (`__init__(self, params={'a': 'b'}, command)`) which Python prohibits.

## 2. Investigation
The investigation tested two hypotheses to resolve the class definition error. Both were confirmed to be technically viable.

1.  **Hypothesis 1: Refactor the Base Class (Confirmed & Recommended)**
    *   **Description:** This approach refactors the `Action` base class to be a plain (non-dataclass) object. All data fields, including the common `params` field, are moved to the concrete subclasses (`ExecuteAction`, `CreateFileAction`).
    *   **Evidence:** See spike `spikes/debug/01-verify-hypothesis-one/`.
    *   **Outcome:** This resolves the issue at definition time, providing a compile-time fix that is architecturally clean.

2.  **Hypothesis 2: Use `__post_init__` Validation (Confirmed)**
    *   **Description:** This approach keeps the dataclass inheritance structure but works around the `TypeError` by giving the required field (`command`) a default value of `None`. A `__post_init__` method is then added to raise a `ValueError` at runtime if the field is not provided.
    *   **Evidence:** See spike `spikes/debug/02-verify-hypothesis-two/`.
    *   **Outcome:** This is a functional workaround, but it moves the error detection from compile-time to runtime and makes the class's public contract (`command: Optional[str]`) slightly misleading.

## 3. Root Cause
The root cause is a violation of a fundamental Python language rule: in a function signature, all parameters without default values must be defined before any parameters with default values. Python's `dataclass` decorator automatically generates an `__init__` method that follows the order of fields defined in the class. The inheritance model caused the fields to be ordered incorrectly in the generated `__init__` method of the `ExecuteAction` subclass.

## 4. Recommended Action
The recommended solution is to implement the fix from **Hypothesis #1**. The `Action` base class should be a simple, non-dataclass object to serve as a marker or interface. All concrete action subclasses (like `ExecuteAction`) should be dataclasses that explicitly define all of their own fields, ensuring the correct argument order.

A verifier script demonstrating the recommended implementation is located at `spikes/debug/solution_verifier.py`.
