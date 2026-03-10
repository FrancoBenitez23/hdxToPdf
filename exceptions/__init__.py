class CLISoftError(Exception):
    pass


class CommandError(CLISoftError):
    def __init__(self, message: str, command_name: str = "", original_exception: Exception | None = None):
        super().__init__(message)
        self.command_name = command_name
        self.original_exception = original_exception


class PromptAbortedError(CLISoftError):
    def __init__(self, flow_name: str = ""):
        super().__init__(f"Prompt aborted: {flow_name}")
        self.flow_name = flow_name
