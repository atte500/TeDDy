# Outbound Adapter: `SystemEnvironmentAdapter`

**Status:** Implemented

## 1. Purpose

The `SystemEnvironmentAdapter` provides a concrete implementation of the `ISystemEnvironment` port using standard Python library modules (`os`, `shutil`, `subprocess`, `tempfile`).

## 2. Implemented Ports

- `ISystemEnvironment`

## 3. Implementation Details

- **Process Execution:** Uses `subprocess.run` to launch external tools.
- **Temp Files:** Uses `tempfile.NamedTemporaryFile` with `delete=False` to manage file lifecycles across process boundaries.
- **PATH Lookup:** Uses `shutil.which`.
