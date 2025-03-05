import logging

class LoggerSingleton:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LoggerSingleton, cls).__new__(cls, *args, **kwargs)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.logger = logging.getLogger("app_logger")

        # File handler
        file_handler = logging.FileHandler("app.log")  # Save logs to "app.log"
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

        # Console handler
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

        self.logger.addHandler(file_handler)  # Log to file
        self.logger.addHandler(stream_handler)  # Log to console
        self.logger.setLevel(logging.INFO)

    def get_logger(self):
        return self.logger