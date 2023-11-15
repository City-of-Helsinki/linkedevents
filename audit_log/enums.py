from enum import Enum


class Operation(Enum):
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class Role(Enum):
    ADMIN = "ADMIN"
    USER = "USER"
    EXTERNAL = "EXTERNAL"
    SYSTEM = "SYSTEM"
    ANONYMOUS = "ANONYMOUS"


class Status(Enum):
    SUCCESS = "SUCCESS"
