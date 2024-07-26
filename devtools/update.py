from .logs import get_logger
from .prefix import Prefix

logger = get_logger(__name__)


def check_for_update(prefix: Prefix) -> bool:
    return True


def update_devtools(prefix: Prefix):
    pass
