from fastapi import APIRouter

from app.models.schemas import InputDataContract, WorkflowDefinition
from app.services.architecture import build_system_workflow
from app.services.ingestion import CSVIngestionService

router = APIRouter(prefix="/contracts")


@router.get("/input-schema", response_model=InputDataContract)
async def get_input_schema() -> InputDataContract:
    return CSVIngestionService().get_input_contract()


@router.get("/workflow", response_model=WorkflowDefinition)
async def get_workflow_definition() -> WorkflowDefinition:
    return build_system_workflow()
