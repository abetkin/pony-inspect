
from .cli import Command

import os
from contextlib import ExitStack

with ExitStack() as stack:
    if os.environ.get('DEBUG'):
        import ipdb
        stack.enter_context(
            ipdb.launch_ipdb_on_exception()
        )
            

    for line in Command().get_output():
        print(line)