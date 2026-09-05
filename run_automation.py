"""Point d'entree historique : unique par defaut, worker avec --worker."""
import sys

from automation_worker import main


if __name__ == "__main__":
    arguments = [] if "--worker" in sys.argv[1:] else ["--once"]
    raise SystemExit(main(arguments))
