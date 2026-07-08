import logging
import sys

# Setup standard formatting
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Create console handler
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)

# Configure the logger
logger = logging.getLogger("vantly")
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)
logger.propagate = False
