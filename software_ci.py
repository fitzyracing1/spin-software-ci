"""spin-software-ci: Read a GitHub Actions workflow or log and flag common failure causes by rules"""
import sys

INTRO = (
    "spin-software-ci by Joshua Almeida.\n"
    "The checker ships in a pull request. It will read a workflow YAML or a job log and print LIT or DARK with the rules that fired.\n"
    "Sponsor: https://github.com/sponsors/fitzyracing1"
)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    print(INTRO)
    if argv and argv[0] in ("-h", "--help", "help"):
        print()
        print("Usage: python software_ci.py")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
