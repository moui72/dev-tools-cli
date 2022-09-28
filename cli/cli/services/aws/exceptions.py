class DevAWSConfigServiceException(Exception):
    pass


class NeedAuth(DevAWSConfigServiceException):
    pass


class NoCachedTokens(NeedAuth):
    pass


class ExpiredCredentials(NeedAuth):
    def __init__(self, *args, expires, **kwargs):
        super().__init__(self, *args, **kwargs)
        self.expires = expires


class InvalidProfile(DevAWSConfigServiceException):
    pass


class NoSuchProfile(DevAWSConfigServiceException):
    pass


class NoValidProfileError(DevAWSConfigServiceException):
    pass
