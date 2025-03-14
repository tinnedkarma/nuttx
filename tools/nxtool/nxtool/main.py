#!/usr/bin/env python3
import argparse
from nxtool.cmds.checkpatch import NxCheckpatch


class NxTool():
    def __init__(self):
        self.argparser: argparse.ArgumentParser = argparse.ArgumentParser(
            description="My CLI tool"
        )

        self.argsubparser = self.argparser.add_subparsers(
            title='commands',
            required=True
        )

        self.nxstyle: NxCheckpatch = NxCheckpatch(self.argsubparser)

    def run(self):
        """
        NxTool command entry point
        """
        args: argparse.Namespace = self.argparser.parse_args()
        args.func(args)
