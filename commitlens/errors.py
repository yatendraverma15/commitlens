import logging

from flask import Flask, jsonify

logger = logging.getLogger(__name__)


class APIError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(APIError)
    def _handle_api_error(e: APIError):
        return jsonify({"error": e.message}), e.status

    @app.errorhandler(Exception)
    def _handle_unexpected(e: Exception):
        logger.exception("unexpected error")
        return jsonify({"error": f"Unexpected error: {str(e)[:200]}"}), 500
