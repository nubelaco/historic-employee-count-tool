class NoCurrentDataException(ValueError):
    def __int__(self, *args):
        super().__init__("Current employee count is 0, so no meaningful data is available", *args)
