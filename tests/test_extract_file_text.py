from shared import extract_file_text


def test_txt_passthrough():
    out = extract_file_text(b"hello world", "notes.txt")
    assert out == "hello world"


def test_md_passthrough():
    out = extract_file_text(b"# Heading\n\nbody", "notes.md")
    assert out == "# Heading\n\nbody"


def test_csv_passthrough():
    out = extract_file_text(b"a,b,c\n1,2,3", "data.csv")
    assert out == "a,b,c\n1,2,3"


def test_txt_handles_invalid_utf8():
    out = extract_file_text(b"valid \xff\xfe bytes", "bad.txt")
    assert "valid" in out and "bytes" in out


def test_unsupported_extension():
    out = extract_file_text(b"...", "weird.xyz")
    assert out.startswith("[Unsupported file type")
