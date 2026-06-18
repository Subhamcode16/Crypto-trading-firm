import os
import sys
import importlib
import logging
from pathlib import Path
from unittest.mock import MagicMock

# Setup simple logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger('deep_tester')

# Add backend/src and backend/ to path
project_root = Path(__file__).parent
src_path = project_root / 'src'
sys.path.insert(0, str(project_root))

def run_deep_tests():
    """Scan all .py files in src and attempt to import AND instantiate them"""
    success_count = 0
    import_failure_count = 0
    runtime_failure_count = 0
    failures = []

    # Mock objects for instantiation tests
    mock_config = MagicMock()
    mock_db = MagicMock()
    mock_telegram = MagicMock()
    
    # Configure mock_config to behave like the real one
    mock_config.get_optional_secret.return_value = None
    mock_config.get_secret.return_value = "mock_secret"
    mock_config.get.return_value = {}
    mock_config.to_dict.return_value = {}

    # Get all .py files recursively in src
    for root, dirs, files in os.walk(src_path):
        if '__pycache__' in root:
            continue
            
        for file in files:
            if file.endswith('.py') and not file.startswith('test_'):
                # Construct relative path from src/
                rel_path = os.path.relpath(os.path.join(root, file), src_path)
                
                # Convert path to module name
                module_name = 'src.' + rel_path[:-3].replace(os.sep, '.')
                if module_name.endswith('.__init__'):
                    module_name = module_name[:-9]
                
                if module_name in ['src.main', 'src.server', 'src.ml.trainer']:
                     # These might start heavy loops/servers/ML loads
                     continue

                logger.info(f"--- Testing: {module_name} ---")
                try:
                    # 1. IMPORT TEST
                    module = importlib.import_module(module_name)
                    success_count += 1
                    
                    # 2. DEEP INSTANTIATION TEST
                    # Find any class that looks like an Agent, Bot, or Manager
                    for attr_name in dir(module):
                        if any(suffix in attr_name for suffix in ['Agent', 'Bot', 'Manager', 'Analyst', 'Aggregator', 'Sentinel', 'Tracker']):
                            cls = getattr(module, attr_name)
                            if isinstance(cls, type) and cls.__module__ == module_name:
                                try:
                                    logger.info(f"   Instantiating {attr_name}...")
                                    # Match signatures from main.py or common patterns
                                    if attr_name == 'TradingBot':
                                        cls(db_client=mock_db)
                                    elif attr_name == 'Agent7RiskManager':
                                        cls(starting_capital=10.0)
                                    elif attr_name == 'Agent6MacroSentinel':
                                        cls()
                                    elif 'Analyst' in attr_name and 'Performance' not in attr_name:
                                        # Agent 2 OnChainAnalyst takes config as dict
                                        cls(config=mock_config.to_dict())
                                    elif 'Aggregator' in attr_name:
                                        cls(config=mock_config.to_dict())
                                    elif 'Tracker' in attr_name:
                                        cls(config=mock_config.to_dict())
                                    else:
                                        # Try generic fallback ladder
                                        try:
                                            cls(config=mock_config, db=mock_db)
                                        except (TypeError, Exception):
                                            try:
                                                cls(db=mock_db, telegram=mock_telegram)
                                            except (TypeError, Exception):
                                                try:
                                                    cls()
                                                except (TypeError, Exception):
                                                    cls(config=mock_config)
                                except Exception as e:
                                    logger.error(f"   [RUNTIME ERROR] {attr_name} failed: {e}")
                                    runtime_failure_count += 1
                                    failures.append((f"{module_name}.{attr_name}", str(e)))

                except (ImportError, ModuleNotFoundError) as e:
                    logger.error(f"FAILED to import {module_name}: {e}")
                    import_failure_count += 1
                    failures.append((module_name, str(e)))
                except Exception as e:
                    logger.error(f"FATAL error in {module_name}: {e}")
                    import_failure_count += 1
                    failures.append((module_name, str(e)))

    logger.info("=" * 30)
    logger.info(f"DEEP VERIFICATION COMPLETE")
    logger.info(f"Import Success: {success_count}")
    logger.info(f"Import Failures: {import_failure_count}")
    logger.info(f"Runtime Init Failures: {runtime_failure_count}")
    
    # Final summary to file
    with open('backend/verification_report.txt', 'w') as f:
        f.write("DEEP VERIFICATION REPORT\n")
        f.write("=" * 30 + "\n")
        f.write(f"Import Success: {success_count}\n")
        f.write(f"Import Failures: {import_failure_count}\n")
        f.write(f"Runtime Init Failures: {runtime_failure_count}\n\n")
        if failures:
            f.write("Failures Details:\n")
            for mod, err in failures:
                f.write(f" - {mod}: {err}\n")
    
    logger.info("=" * 30)
    logger.info(f"DEEP VERIFICATION COMPLETE - Report saved to backend/verification_report.txt")
    return (import_failure_count == 0 and runtime_failure_count == 0)

if __name__ == "__main__":
    if run_deep_tests():
        logger.info("✅ SYSTEM PASS: All modules import and instantiate correctly.")
        sys.exit(0)
    else:
        logger.error("❌ SYSTEM FAIL: Issues detected in codebase.")
        sys.exit(1)
