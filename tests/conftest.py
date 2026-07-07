"""
pytest configuration for the SME Productivity Assessment Platform.
Sets up asyncio mode for async test functions.
"""


def pytest_configure(config):
    """Register asyncio mode for all async tests."""
    config.addinivalue_line("markers", "asyncio: mark test as an async coroutine")
