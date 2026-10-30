"""Keep tests out of the user's real Mouser log.

Importing main_qml runs core.log_setup.setup_logging(), which redirects
stdout into ~/Library/Logs/Mouser/mouser.log (or the platform equivalent)
for the rest of the process. Under the test runner that appended every
test's output to the log of the Mouser the user is actually running.
setup_logging() is a no-op once the root logger has a handler, so import
this module before main_qml.
"""

import logging

logging.getLogger().addHandler(logging.NullHandler())
