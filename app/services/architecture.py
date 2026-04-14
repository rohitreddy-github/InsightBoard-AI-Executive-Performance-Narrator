from app.models.schemas import WorkflowDefinition, WorkflowStage


def build_system_workflow() -> WorkflowDefinition:
    return WorkflowDefinition(
        name="Ingestion -> Processing -> Visualization -> Prompt Assembly -> LLM Inference -> Output",
        stages=[
            WorkflowStage(
                step=1,
                name="ingestion",
                input_artifacts=["CSV upload"],
                output_artifacts=["validated KPI records", "canonical long-format dataframe"],
                purpose="Read the CSV, validate the date/metric_name/value contract, and normalize row structure.",
            ),
            WorkflowStage(
                step=2,
                name="processing",
                input_artifacts=["validated KPI records"],
                output_artifacts=["daily normalized series", "pivoted metric matrix", "metric snapshots", "anomaly signals"],
                purpose="Clean missing values, collapse duplicates, and aggregate KPI observations into weekly or monthly analytical features.",
            ),
            WorkflowStage(
                step=3,
                name="visualization",
                input_artifacts=["metric snapshots", "optional chart image"],
                output_artifacts=["chart context summary"],
                purpose="Explain chart trends and align visual evidence with structured KPI movement.",
            ),
            WorkflowStage(
                step=4,
                name="prompt_assembly",
                input_artifacts=["metric snapshots", "anomaly signals", "chart context summary"],
                output_artifacts=["LLM-ready prompt payload"],
                purpose="Assemble business context into a deterministic prompt structure for the model layer.",
            ),
            WorkflowStage(
                step=5,
                name="llm_inference",
                input_artifacts=["LLM-ready prompt payload"],
                output_artifacts=["executive narrative draft", "recommended actions"],
                purpose="Generate executive-facing commentary from validated analytical context.",
            ),
            WorkflowStage(
                step=6,
                name="output",
                input_artifacts=["executive narrative draft", "recommended actions"],
                output_artifacts=["report API response"],
                purpose="Return a structured executive summary payload for downstream UI or reporting use.",
            ),
        ],
    )
