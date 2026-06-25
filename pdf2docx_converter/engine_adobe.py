"""Cloud conversion engine: Adobe PDF Services "Export PDF" (PDF -> DOCX).

Optional, higher-fidelity engine for design-heavy / complex documents where the
local pdf2docx engine struggles (vector graphics, Type3 fonts, multi-column).

⚠️  This engine UPLOADS the PDF to Adobe's cloud. Do not use it for documents
that may not leave your machine. The local engine stays fully offline.

Credentials (free tier: https://developer.adobe.com/document-services/) are read
from, in order:
  1. env vars  PDF_SERVICES_CLIENT_ID / PDF_SERVICES_CLIENT_SECRET
  2. a .env file in the project root (same names)
  3. pdfservices-api-credentials.json downloaded from the Adobe console

Requires the optional dependency:  pip install -r requirements-adobe.txt
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from .config import PROJECT_ROOT

logger = logging.getLogger(__name__)

# Adobe's conventional env var names.
ENV_CLIENT_ID = "PDF_SERVICES_CLIENT_ID"
ENV_CLIENT_SECRET = "PDF_SERVICES_CLIENT_SECRET"


class AdobeConfigError(RuntimeError):
    """Missing/invalid credentials or the SDK isn't installed."""


class AdobeConversionError(RuntimeError):
    """The Adobe service failed to convert the document."""


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE per line) — avoids an extra dependency."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _resolve_credentials() -> tuple[str, str]:
    """Find client_id/client_secret from env, .env, or the Adobe JSON file."""
    _load_dotenv(PROJECT_ROOT / ".env")

    client_id = os.environ.get(ENV_CLIENT_ID)
    client_secret = os.environ.get(ENV_CLIENT_SECRET)

    if not (client_id and client_secret):
        json_path = PROJECT_ROOT / "pdfservices-api-credentials.json"
        if json_path.exists():
            data = json.loads(json_path.read_text(encoding="utf-8"))
            creds = data.get("client_credentials", data)
            client_id = client_id or creds.get("client_id")
            client_secret = client_secret or creds.get("client_secret")

    if not (client_id and client_secret):
        raise AdobeConfigError(
            "Adobe credentials not found. Set "
            f"{ENV_CLIENT_ID}/{ENV_CLIENT_SECRET} (env or .env), or place "
            "pdfservices-api-credentials.json in the project root. "
            "Get free keys at https://developer.adobe.com/document-services/"
        )
    return client_id, client_secret


def convert_file(
    pdf_path: str | Path,
    docx_path: str | Path,
    ocr_locale: str = "ru-RU",
) -> Path:
    """Convert a single PDF to DOCX via Adobe's cloud. Returns the output path."""
    try:
        from adobe.pdfservices.operation.auth.service_principal_credentials import (
            ServicePrincipalCredentials,
        )
        from adobe.pdfservices.operation.exception.exceptions import (
            SdkException,
            ServiceApiException,
            ServiceUsageException,
        )
        from adobe.pdfservices.operation.pdf_services import PDFServices
        from adobe.pdfservices.operation.pdf_services_media_type import (
            PDFServicesMediaType,
        )
        from adobe.pdfservices.operation.pdfjobs.jobs.export_pdf_job import ExportPDFJob
        from adobe.pdfservices.operation.pdfjobs.params.export_pdf.export_ocr_locale import (
            ExportOCRLocale,
        )
        from adobe.pdfservices.operation.pdfjobs.params.export_pdf.export_pdf_params import (
            ExportPDFParams,
        )
        from adobe.pdfservices.operation.pdfjobs.params.export_pdf.export_pdf_target_format import (
            ExportPDFTargetFormat,
        )
        from adobe.pdfservices.operation.pdfjobs.result.export_pdf_result import (
            ExportPDFResult,
        )
    except ImportError as exc:
        raise AdobeConfigError(
            "Adobe SDK is not installed. Run: pip install -r requirements-adobe.txt"
        ) from exc

    pdf_path = Path(pdf_path)
    docx_path = Path(docx_path)
    docx_path.parent.mkdir(parents=True, exist_ok=True)

    client_id, client_secret = _resolve_credentials()

    # Map locale string -> SDK enum (fallback to EN_US if unknown).
    locale = {
        "ru-RU": ExportOCRLocale.RU_RU,
        "en-US": ExportOCRLocale.EN_US,
        "en-GB": ExportOCRLocale.EN_GB,
    }.get(ocr_locale, ExportOCRLocale.EN_US)

    logger.warning("Uploading %s to Adobe cloud for conversion…", pdf_path.name)
    try:
        credentials = ServicePrincipalCredentials(
            client_id=client_id, client_secret=client_secret
        )
        pdf_services = PDFServices(credentials=credentials)

        input_asset = pdf_services.upload(
            input_stream=pdf_path.read_bytes(),
            mime_type=PDFServicesMediaType.PDF,
        )
        export_params = ExportPDFParams(
            target_format=ExportPDFTargetFormat.DOCX, ocr_lang=locale
        )
        job = ExportPDFJob(input_asset=input_asset, export_pdf_params=export_params)

        location = pdf_services.submit(job)
        response = pdf_services.get_job_result(location, ExportPDFResult)
        result_asset = response.get_result().get_asset()
        stream_asset = pdf_services.get_content(result_asset)

        docx_path.write_bytes(stream_asset.get_input_stream())
    except (ServiceApiException, ServiceUsageException, SdkException) as exc:
        raise AdobeConversionError(
            f"Adobe failed to convert {pdf_path.name}: {exc}"
        ) from exc

    if not docx_path.exists() or docx_path.stat().st_size == 0:
        raise AdobeConversionError(f"Adobe returned no output for {pdf_path.name}")
    return docx_path
