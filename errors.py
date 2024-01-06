class UserNotFound(Exception):
    def __str__(self):
        return "User is not found"


class WrongCommandFormat(Exception):
    def __str__(self):
        return "Wrong command format"


class CommandIsAlreadyExist(Exception):
    def __str__(self):
        return "Command is already exist"


class CmdNotFound(Exception):
    def __str__(self):
        return "Command is not found"


class UserNotActive(Exception):
    def __str__(self):
        return "User is not active"


class VerifyCodeWrong(Exception):
    def __str__(self):
        return "Verify Code is wrong!"
