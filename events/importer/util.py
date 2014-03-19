from django.utils.translation.trans_real import activate, deactivate

class active_language:
    def __init__(self, language):
        self.language = language
    def __enter__(self):
        activate(self.language)
        return self.language
    def __exit__(self, type, value, traceback):
        deactivate()
