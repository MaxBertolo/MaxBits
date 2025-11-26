from pathlib import Path
import pdfkit


def html_to_pdf(html_content: str, output_path: str) -> str:
    """
    Converte una stringa HTML in PDF usando wkhtmltopdf.
    Restituisce il percorso del PDF creato.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pdfkit.from_string(html_content, str(output_path))
    return str(output_path)
