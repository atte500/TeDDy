import os
from unittest.mock import MagicMock
from teddy_executor.core.services.context_service import ContextService
from teddy_executor.adapters.outbound.local_file_system_adapter import LocalFileSystemAdapter
from teddy_executor.core.services.edit_simulator import EditSimulator

def trace_execution():
    # Simulation of what SessionOrchestrator does
    # 1. It gets context_files from SessionService
    # Based on user's cat output, this is a DICT of paths:
    context_files = {
        "Session": ["README.md", "docs/project/PROJECT.md"],
        "Turn": ["plan.md", "report.md"]
    }
    
    print(f"DEBUG: SessionOrchestrator sending: {context_files}")
    
    # 2. It calls ContextService.get_context
    fs_adapter = LocalFileSystemAdapter(EditSimulator(), root_dir=".")
    
    # Let's see what ContextService._resolve_scoped_paths does with this
    service = ContextService(fs_adapter, MagicMock(), MagicMock(), MagicMock())
    
    print("DEBUG: ContextService resolving paths...")
    scoped_paths, all_resolved = service._resolve_scoped_paths(context_files)
    print(f"DEBUG: Scoped paths resolved to: {scoped_paths}")

if __name__ == "__main__":
    trace_execution()