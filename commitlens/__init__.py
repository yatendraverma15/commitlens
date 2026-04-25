import logging
from pathlib import Path

from flask import Flask


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )


def create_app() -> Flask:
    _setup_logging()

    repo_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        static_folder=str(repo_root / "static"),
        template_folder=str(repo_root / "templates"),
    )

    from commitlens.config import GITHUB_TOKEN
    from commitlens.errors import register_error_handlers
    from commitlens.routes import bp

    logger = logging.getLogger("commitlens")
    logger.info(
        "GitHub auth: %s",
        "enabled" if GITHUB_TOKEN else "disabled (public repos only)",
    )

    register_error_handlers(app)
    app.register_blueprint(bp)
    return app
