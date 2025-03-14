import sys
from pathlib import Path
from nxtool.nxstyle.nxstyle import Checker, CChecker

try:
    file_path: Path = Path(sys.argv[1])
except IndexError:
    print("No argument provided")
    sys.exit(1)

if file_path.resolve().is_file():
    match file_path.suffix:
        case '.c':
            checker: Checker = CChecker(file_path, 'c.scm')

        case '.h':
            pass

        case _:
            sys.exit(1)

    checker.check_style()
else:
    print("Not a valid file path")
    sys.exit(1)

sys.exit(0)
