class SSOConfigException(Exception):
    pass


class GoogleRoleUsedWithSSOCommand(SSOConfigException):
    pass


class BadEnvInRole(SSOConfigException):
    pass
