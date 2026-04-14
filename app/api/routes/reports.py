from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.models.schemas import MissingValueStrategy, ReportResponse, TimeAggregation
from app.prompts.system_prompts import PersonaRole
from app.services.ingestion import InputContractError
from app.services.pipeline import build_report_pipeline

router = APIRouter()
public_router = APIRouter()
settings = get_settings()


async def _generate_report_impl(
    csv_file: Annotated[UploadFile, File(description="Structured KPI data in CSV format")],
    report_title: Annotated[
        str | None,
        Form(description="Optional executive report title"),
    ] = None,
    aggregation_granularity: Annotated[
        TimeAggregation,
        Form(description="Time bucket for preprocessing and trend analysis."),
    ] = settings.default_aggregation_granularity,
    missing_value_strategy: Annotated[
        MissingValueStrategy,
        Form(description="How missing daily values should be handled before aggregation."),
    ] = settings.default_missing_value_strategy,
    chart_image: Annotated[
        UploadFile | None,
        File(description="Optional chart image for multimodal explanation"),
    ] = None,
    persona: Annotated[
        PersonaRole,
        Form(description="Executive persona used for prompt framing."),
    ] = PersonaRole.CFO,
) -> ReportResponse:
    if not csv_file.filename or not csv_file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV uploads are supported.")

    csv_bytes = await csv_file.read()
    if not csv_bytes:
        raise HTTPException(status_code=400, detail="CSV upload is empty.")

    chart_bytes = await chart_image.read() if chart_image is not None else None
    chart_mime_type = chart_image.content_type if chart_image is not None else None
    pipeline = build_report_pipeline()

    try:
        return await run_in_threadpool(
            pipeline.generate_report,
            report_title or "Monthly Executive Performance Summary",
            csv_bytes,
            csv_file.filename,
            aggregation_granularity,
            missing_value_strategy,
            chart_bytes,
            chart_mime_type,
            persona,
        )
    except InputContractError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/generate", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def generate_report(
    csv_file: Annotated[UploadFile, File(description="Structured KPI data in CSV format")],
    report_title: Annotated[
        str | None,
        Form(description="Optional executive report title"),
    ] = None,
    aggregation_granularity: Annotated[
        TimeAggregation,
        Form(description="Time bucket for preprocessing and trend analysis."),
    ] = settings.default_aggregation_granularity,
    missing_value_strategy: Annotated[
        MissingValueStrategy,
        Form(description="How missing daily values should be handled before aggregation."),
    ] = settings.default_missing_value_strategy,
    chart_image: Annotated[
        UploadFile | None,
        File(description="Optional chart image for multimodal explanation"),
    ] = None,
    persona: Annotated[
        PersonaRole,
        Form(description="Executive persona used for prompt framing."),
    ] = PersonaRole.CFO,
) -> ReportResponse:
    return await _generate_report_impl(
        csv_file=csv_file,
        report_title=report_title,
        aggregation_granularity=aggregation_granularity,
        missing_value_strategy=missing_value_strategy,
        chart_image=chart_image,
        persona=persona,
    )


@public_router.post("/generate-report", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def generate_report_public(
    csv_file: Annotated[UploadFile, File(description="Structured KPI data in CSV format")],
    report_title: Annotated[
        str | None,
        Form(description="Optional executive report title"),
    ] = None,
    aggregation_granularity: Annotated[
        TimeAggregation,
        Form(description="Time bucket for preprocessing and trend analysis."),
    ] = settings.default_aggregation_granularity,
    missing_value_strategy: Annotated[
        MissingValueStrategy,
        Form(description="How missing daily values should be handled before aggregation."),
    ] = settings.default_missing_value_strategy,
    chart_image: Annotated[
        UploadFile | None,
        File(description="Optional chart image for multimodal explanation"),
    ] = None,
    persona: Annotated[
        PersonaRole,
        Form(description="Executive persona used for prompt framing."),
    ] = PersonaRole.CFO,
) -> ReportResponse:
    return await _generate_report_impl(
        csv_file=csv_file,
        report_title=report_title,
        aggregation_granularity=aggregation_granularity,
        missing_value_strategy=missing_value_strategy,
        chart_image=chart_image,
        persona=persona,
    )
