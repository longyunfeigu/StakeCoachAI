import pytest
from infrastructure.external.document_parser.parser import FileDocumentParser


@pytest.fixture
def parser():
    return FileDocumentParser()


class TestFileDocumentParser:
    @pytest.mark.asyncio
    async def test_parse_txt_fallback(self, parser):
        content = b"Hello World\nThis is a test document."
        result = await parser.parse(content, "test.txt")
        assert result.raw_text == "Hello World\nThis is a test document."
        assert result.title == "test"

    @pytest.mark.asyncio
    async def test_unsupported_format_raises(self, parser):
        with pytest.raises(ValueError, match="Unsupported"):
            await parser.parse(b"data", "test.zip")

    @pytest.mark.asyncio
    async def test_extract_key_data_finds_numbers(self, parser):
        content = b"Revenue grew 30% to $5M. Team expanded from 10 to 25 people."
        result = await parser.parse(content, "report.txt")
        assert any("30%" in d for d in result.key_data)
