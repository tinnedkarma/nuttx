"""

"""
from argparse import Namespace
from pathlib import Path
import sys
import shutil
import pty
import importlib.resources


class NxCheckpatch():
    """
    NxTool command class for nuttx code checker.
    This class handles subparser named "checkpatch"
    It configures the argparser arguments and entrypoint 
    
    :param subparser: The subparser instance given by the NxTool class
    :type subparser: _SubParsersAction[ArgumentParser]
    """
    def __init__(self, subparser) -> None:
        self.argparser = subparser.add_parser(
            "checkpatch",
            help="Greet the user"
        )

        self.argparser.add_argument(
            "--spell",
            action = "store_true",
            help = "Check code spelling"
        )

        self.argparser.add_argument(
            "--encode",
            action = "store_true",
            help = "Check code encoding"
        )

        self.argparser.add_argument(
            "file",
            type=Path,
            help="File to check"
        )

        self.argparser.set_defaults(func=self.__run)

    def __run(self, args: Namespace) -> None:
        """
        This method is an entrypoint for "checkpatch" subcommand.
        It gets called indirectly using ```args.func(args)```
        from NxTool class
        
        :param args: Attribute storage resolved by argparge
        :type args: Namespace
        """
        file_path:Path = Path(args.file)

        if args.spell is True:
            pty.spawn([
                "codespell",
                "-q", "7",
                str(file_path)
            ])
            sys.exit(0)

        if args.encode is True:
            pty.spawn([
                "cvt2utf",
                "convert", "--nobak",
                str(file_path)
            ])
            sys.exit(0)

        match file_path.suffix:

            case '.rs':
                if shutil.which("rustfmt") is not None:
                    pty.spawn([
                        "rustfmt",
                        "--edition", "2021",
                        "--check",
                        str(file_path)
                    ])
                else:
                    sys.exit(1)

            case '.py':
                with importlib.resources.path("nxtool.nxstyle.config", "setup.cfg") as config_path:
                    pty.spawn([
                        "python", "-m",
                        "flake8", "--config", str(config_path),
                        str(file_path)
                    ])

            case '.cmake':
                pty.spawn([
                    "python", "-m", "cmakelang.lint", str(file_path)
                ])

            # Here we should also handle the hardcoded names
            case _:
                if file_path.name == 'CMakeLists.txt':
                    with importlib.resources.path("nxstyle.config", "setup.cfg") as config_path:
                        pty.spawn([
                            "python", "-m",
                            "flake8", "--config", f"{config_path}",
                            str(file_path)
                        ])

                sys.exit(1)
