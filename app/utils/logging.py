# =============================================
# File: app/utils/logging.py
# Purpose: Logging configuration
# =============================================

from loguru import logger
logger.add("logs/app.log", rotation="10 MB")
