# Validation Rules

Validation is split into two layers:

## Pydantic Model Validation

The models enforce type constraints and field ranges, including:

- required nested model structure for `Incident`
- numeric bounds for scores such as severity and confidence
- non-empty canonical fields where applicable

## Schema Validation Utilities

`src/ingestion/validators.py` provides structured validation helpers that:

- generate JSON Schema artifacts for `Incident`, `AIAnalysis`, `Theme`, and `VectorMetadata`
- return normalized issue records with `code`, `severity`, `field`, `message`, `value`, and `expected`
- validate canonical enum values for patient sex, procedure type, outcome severity, and outcome category
- warn on non-canonical monitoring labels
- flag weak incident context when both description and details are empty

## Validation Status

`AIAnalysis.validation_status` accepts:

- `pending`
- `valid`
- `invalid`
- `needs_review`
