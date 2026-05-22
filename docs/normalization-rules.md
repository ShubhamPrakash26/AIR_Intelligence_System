# Normalization Rules

The normalization engine converts raw spreadsheet values into canonical values before validation.

## Missing Values

The following tokens are treated as missing and converted to `None`:

- empty strings
- `-`
- `--`
- `na`
- `n/a`
- `none`
- `null`
- `nan`
- `not available`

## Boolean Values

- True tokens: `yes`, `y`, `true`, `t`, `1`, `present`
- False tokens: `no`, `n`, `false`, `f`, `0`, `absent`

## Dates

Supported input formats include:

- `dd-mm-yyyy`
- `dd/mm/yyyy`
- `yyyy-mm-dd`
- `dd-mm-yy`
- `dd/mm/yy`

## Canonical Mapping

- Sex values are normalized to `Male`, `Female`, `Other`, or `Unknown`.
- Procedure type values are normalized to `Elective` or `Emergency`.
- Outcome categories are normalized to `A` through `E`, including subcategory tokens such as `D1` and `D2`.
- Surgical branch labels are mapped to the canonical branch taxonomy.
- Incident type labels are mapped to canonical multi-label categories.
- Monitoring labels are normalized to the canonical monitoring vocabulary.

## Lists

Comma-separated or semicolon-separated text is converted to lists, whitespace is trimmed, and duplicate normalized values are removed.
