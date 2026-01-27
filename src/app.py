import os

import typer
from dotenv import load_dotenv
from loguru import logger

from library import log

if not load_dotenv():
    logger.warning("Failed to load .env file")

app = typer.Typer(pretty_exceptions_enable=False, pretty_exceptions_show_locals=True)


@app.command()
def main(required_arg: str, optional_arg: str | None = None) -> None:
    logger.info(f"Hello! {required_arg=}, {optional_arg=}")
    logger.info(f"PYTHONPATH={os.getenv('PYTHONPATH', 'Not set')}")
    logger.info(f"LOG_STDERR_LEVEL={os.getenv('LOG_STDERR_LEVEL', 'Not set. Copy `.env_template` to `.env`')}")
    logger.info(f"LOG_FILE_LEVEL={os.getenv('LOG_FILE_LEVEL', 'Not set. Copy `.env_template` to `.env`')}")
    # raise NotImplementedError("app.main() not implemented")


if __name__ == "__main__":
    log.configure()
    app()
