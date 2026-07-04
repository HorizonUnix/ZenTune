#!/usr/bin/env python3
import os
import sys

_ROOT = os.path.dirname(os.path.realpath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from Assets.relay.app import run_relay

if __name__ == "__main__":
    run_relay()
