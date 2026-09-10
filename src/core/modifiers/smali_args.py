"""Smali patching arguments helper."""


class SmaliArgs:
    """Arguments for SmaliKit patching operations."""
    
    def __init__(self, **kwargs):
        self.path = None
        self.file_path = None
        self.method = None
        self.seek_keyword = None
        self.iname = None
        self.remake = None
        self.replace_in_method = None
        self.regex_replace = None
        self.delete_in_method = None
        self.delete_method = False
        self.after_line = None
        self.before_line = None
        self.insert_line = None
        self.recursive = False
        self.return_type = None
        self.append_method = None
        
        self.__dict__.update(kwargs)
