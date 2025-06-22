import re
import base64
import quopri
import hashlib
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class MHTMLToSingleHTML:
    def __init__(self, mhtml_path, output_html_path):
        self.mhtml_path = mhtml_path
        self.output_html_path = output_html_path
        self.boundary = None
        self.url_to_data_uri = {}
        self.main_html = None

    def _decode_body(self, encoding, body):
        try:
            if encoding == "base64":
                return base64.b64decode(body)
            elif encoding == "quoted-printable":
                return quopri.decodestring(body)
            return body.encode("utf-8")
        except Exception as e:
            logging.warning(f"Decoding error: {e}")
            return body.encode("utf-8")

    def _parse_boundary(self, headers):
        match = re.search(r'boundary="([^"]+)"', headers)
        return match.group(1) if match else None

    def _make_data_uri(self, content_type, binary_data):
        base64_data = base64.b64encode(binary_data).decode("utf-8")
        return f"data:{content_type};base64,{base64_data}"

    def _extract_parts(self, content):
        header_end = content.find("\n\n")
        if header_end == -1:
            raise ValueError("Invalid MHTML structure")
        header_block = content[:header_end]
        self.boundary = self._parse_boundary(header_block)
        if not self.boundary:
            raise ValueError("No boundary found in MHTML headers")

        boundary = "--" + self.boundary
        parts = content.split(boundary)
        return parts[1:-1]

    def _process_part(self, part):
        part = part.strip().lstrip("\r\n")
        if not part:
            return
        headers, _, body = part.partition("\n\n")

        headers = headers.replace("\r\n", "\n")
        body = body.replace("\r\n", "\n")

        content_type_match = re.search(r"Content-Type: ([^\n;]+)", headers, re.IGNORECASE)
        encoding_match = re.search(r"Content-Transfer-Encoding: ([^\n]+)", headers, re.IGNORECASE)
        location_match = re.search(r"Content-Location: ([^\n]+)", headers, re.IGNORECASE)
        cid_match = re.search(r"Content-ID: <([^>]+)>", headers, re.IGNORECASE)

        content_type = content_type_match.group(1).strip() if content_type_match else "application/octet-stream"
        encoding = encoding_match.group(1).strip().lower() if encoding_match else "7bit"

        decoded = self._decode_body(encoding, body)

        if content_type.startswith("text/html") and self.main_html is None:
            try:
                self.main_html = decoded.decode("utf-8")
            except:
                self.main_html = decoded.decode("latin-1")
            return

        data_uri = self._make_data_uri(content_type, decoded)

        if location_match:
            location = location_match.group(1).strip()
            self.url_to_data_uri[location] = data_uri

        if cid_match:
            cid = "cid:" + cid_match.group(1).strip()
            self.url_to_data_uri[cid] = data_uri

    def _replace_links(self):
        html = self.main_html

        for original in sorted(self.url_to_data_uri.keys(), key=len, reverse=True):
            data_uri = self.url_to_data_uri[original]
            html = html.replace(original, data_uri)
        return html

    def convert(self):
        with open(self.mhtml_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        parts = self._extract_parts(content)

        for part in parts:
            self._process_part(part)

        if self.main_html is None:
            logging.error("Main HTML part not found.")
            return

        final_html = self._replace_links()

        with open(self.output_html_path, "w", encoding="utf-8") as f:
            f.write(final_html)

        logging.info(f"Saved HTML to: {self.output_html_path}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert MHTML to single self-contained HTML.")
    parser.add_argument("mhtml", help="Input .mhtml file")
    parser.add_argument("output", help="Output .html file")

    args = parser.parse_args()

    converter = MHTMLToSingleHTML(args.mhtml, args.output)
    converter.convert()
