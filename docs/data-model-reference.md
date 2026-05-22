# Data Model Reference

This document summarizes the primary Pydantic models used by the AIR Clinical Incident Intelligence Engine.

## Incident

`Incident` is the canonical parsed record produced by the Excel parser. It groups:

- `patient`: demographic details such as age range, sex, BMI, and ASA grade.
- `surgery`: procedure metadata such as procedure type, branch, and specific procedure.
- `incident`: the narrative and structured incident details.
- `anesthesia`: anesthesia technique and monitoring labels.
- `outcome`: AIR outcome category and harm information.
- `metadata`: source file and upload metadata.

## AIAnalysis

`AIAnalysis` stores downstream AI output for a single incident. Core fields include:

- `incident_id`
- `incident_type`
- `severity`
- `severity_score`
- `root_cause`
- `contributing_factors`
- `contributing_factor_categories`
- `key_learning`
- `preventive_recommendations`
- `confidence_score`
- `validation_status`
- `validation_errors`
- `processing_timestamp`
- `model_version`
- `processing_notes`

## Theme

`Theme` represents clustered incident patterns and is used for theme discovery and summarization.

## VectorMetadata

`VectorMetadata` captures the metadata stored alongside embeddings in the vector store.
