#!/usr/bin/env python3
import argparse


class NxTool():
    def __init__(self):
        self.argparser: argparse.ArgumentParser = argparse.ArgumentParser(
            description="My CLI tool"
        )

        self.argsubparser = self.argparser.add_subparsers(
            title='commands',
            required=True
        )


    def run(self):
        """
        NxTool command entry point
        """
        args: argparse.Namespace = self.argparser.parse_args()
        args.func(args)
