import os


class Unimplemented(Exception):
    def __init__(self):
        pass


def as_plain_text(filename):
    (body, ext) = os.path.splitext(filename)
    ext = ext.lower()
    #if ext == '.docx':
    #    print("Word documents not handled yet")
    #    raise Unimplemented
    #elif ext == '.pdf':
    #    print("PDF (neither with nor without OCR) not handled yet")
    #    raise Unimplemented
    #elif ext in ['.xlsx', '.pptx']:
    #    print("Skipping %s file (%s)" % (ext, filename))
    #    raise Unimplemented
    return open(filename).read()
