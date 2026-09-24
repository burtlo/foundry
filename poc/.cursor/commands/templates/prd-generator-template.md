# PRD Generator Template

This file contains the centralized template for PRD generator prompt files. This template is designed to be used by multiple workflows and customized per repository.

**Template Version:** 3.1 (June 2026)

### Version History
| Version | Date | Changes |
|---------|------|---------|
| 3.1 | June 2026 | Added Environment Data Replication extraction (§4.5 / PRD §3.5), User Workflows refresh cross-ref |
| 3.0 | March 2026 | Added Section 4.4: Store Data Scope extraction, store data source in integration diagram |
| 2.0 | January 2026 | Added Section 9: Testing & Quality Assurance, Test Harness extraction |
| 1.0 | Initial | Original template with sections 1-8 + Appendices |

---

## PRD Generator Prompt File Template

**Location:** `{SolutionRoot}/Documentation/prd-generator-prompt.md`

```markdown
# PRD Orchestrator Agent Instructions

This document contains the instructions for the AI Orchestrator Agent that generates the unified PRD from all AGENTS.md files in the workspace.

## How to Use

When you want to generate or update the PRD, give this prompt to the AI:

```
Read /Documentation/prd-generator-prompt.md and execute those instructions to generate the PRD.
```

Or simply say:
```
Generate the PRD from all AGENTS.md files
```

---

## Agent Role

You are a **PRD Generator Agent**. Your job is to read all AGENTS.md files in the {Application Name} workspace and generate a unified Product Requirements Document.

## Input Files

Read these AGENTS.md files in order:

1. **`/AGENTS.md`** - Root level system overview
{Entry Point List - Add each entry point AGENTS.md file}

## Extraction Rules

From each AGENTS.md, extract and organize:

| Section | What to Extract |
|---------|-----------------|
| `## Application Metadata` | Name, description, ownership, platforms |
| `## Technical Stack` | Framework, language, infrastructure |
| `## Security & Compliance` | Auth, compliance, data classification |
| `## Business Impact` | Users, revenue impact, criticality |
| `## CI/CD` | Platform, workflows, environments, artifacts |
| `## External Interfaces` | APIs exposed, APIs consumed, data flows |
| `## User Workflows` | State diagrams, user journeys, process flows |
| `## Data Contracts` | Key models, schemas, validation rules |
| `## Authentication` | Auth mechanisms per component |
| `## Architecture Overview` | Component structure, dependencies |
| `## Test Harness & Dev Tools` | Test projects, E2E selectors, test utilities, test data setup |
| `## Store Data Scope` | Store data sources, inclusion rules, exclusion rules, filtering mechanisms |
| Root `## Environment Data Replication` | PRD §4.5 — purpose, scope, orchestration stages, replicated entities, config gates, status, notifications; or Not Applicable |
| `## User Workflows` > Environment Data Refresh | PRD §6.4 — sequence diagram, status endpoint, stage names; cross-ref §4.5 |

## Output Structure

Generate the PRD with this exact structure:

```markdown
# {Application Name} - Product Requirements Document

Generated: {current_date}
Source: AGENTS.md files from {Application Name} workspace

---

## 1. System Identity

### 1.1 Overview
| Field | Value |
|-------|-------|
| **System Name** | {From root AGENTS.md} |
| **Description** | {From root AGENTS.md} |
| **Type** | {Application type} |
| **Tech Owner** | {From root AGENTS.md} |
| **Business Owner** | {From root AGENTS.md} |
| **Department** | {From root AGENTS.md} |

### 1.2 Repositories/Components
{List all entry points from root AGENTS.md Entry Point Index}

### 1.3 Key Metrics
| Metric | Value |
|--------|-------|
| **Users per Month** | {From root AGENTS.md} |
| **Criticality** | {From root AGENTS.md} |
| **Revenue Impact** | {From root AGENTS.md} |

---

## 2. Technical Architecture

### 2.1 Technology Stack
| Component | Technology |
|-----------|------------|
{Combine from all AGENTS.md Technical Stack sections}

### 2.2 Infrastructure
| Field | Value |
|-------|-------|
| **Hosting** | {From root AGENTS.md} |
| **Resources** | {From root AGENTS.md} |
| **Source Control** | {From root AGENTS.md} |

### 2.3 Architecture Diagram
{Generate Mermaid diagram showing component interactions}

---

## 3. External Interfaces

### 3.1 APIs Exposed
{Combine from all AGENTS.md ## External Interfaces > APIs Exposed}

### 3.2 APIs Consumed  
{Combine from all AGENTS.md ## External Interfaces > APIs Consumed}

### 3.3 Integration Diagram
{Generate Mermaid diagram showing external integrations}

---

## 4. Data Architecture

### 4.1 Data Classification
| Field | Value |
|-------|-------|
| **Sensitivity** | {From root AGENTS.md} |
| **Data Types** | {From root AGENTS.md} |

### 4.2 Key Data Models
{Combine from all AGENTS.md ## Data Contracts}

### 4.3 API Versioning
- Current version: {version}
- Route prefix: {prefix}

### 4.4 Store Data Scope
{Extract from root AGENTS.md ## Store Data Scope}

| Field | Value |
|-------|-------|
| **Store Data Source(s)** | {From root AGENTS.md Store Data Scope} |
| **Store Scope** | {All stores / Filtered subset} |

#### Inclusion Rules
| Rule Type | Value | Mechanism |
|-----------|-------|-----------|
{From root AGENTS.md Store Data Scope > Store Inclusion Rules}

#### Exclusion Rules
| Rule Type | Value | Mechanism |
|-----------|-------|-----------|
{From root AGENTS.md Store Data Scope > Store Exclusion Rules}

*Note: If the application does not interact with store data, include "Not Applicable" note.*

### 4.5 Environment Data Replication
{Extract from root AGENTS.md ## Environment Data Replication}

| Aspect | Detail |
|--------|--------|
| **Purpose** | {From root AGENTS.md} |
| **Environments** | Non-production only |
| **Trigger** | Manual Admin (`/environmentdatarefresh`) |

#### Orchestration Stages
{From root AGENTS.md > Orchestration Stages table}

#### Replicated Production Data
{From root AGENTS.md > Replicated Production Data table — 8 Cosmos containers in order}

#### Configuration Gates
{From root AGENTS.md > Configuration Gates table — key names only}

#### Status & Notifications
{From root AGENTS.md > Status & History and Notifications subsections}

*Cross-reference PRD User Workflows section for sequence diagram and API endpoints.*

---

## 5. Security & Compliance

### 5.1 Authentication
| Component | Auth Method |
|-----------|-------------|
{Extract from each entry point AGENTS.md ## Authentication}

### 5.2 Compliance
| Requirement | Status |
|-------------|--------|
| **PCI/Other Requirements** | {From root AGENTS.md} |
| **DAST** | {From root AGENTS.md} |
| **SAST** | {From root AGENTS.md} |
| **Security Controls** | {From root AGENTS.md} |

### 5.3 Secret Management
{From root AGENTS.md}

---

## 6. Component Architecture

{For each entry point, create a subsection with:}
### 6.x {Component Name}
{Extract from {Component}/AGENTS.md ## Architecture}

---

## 7. User Workflows

{Extract and combine from all AGENTS.md ## User Workflows sections}

---

## 8. Deployment & Infrastructure

### 8.1 Environments
| Environment | Purpose |
|-------------|---------|
{Combine deployment info from all AGENTS.md}

### 8.2 Azure Resources
{List from root AGENTS.md Infrastructure field}

### 8.3 CI/CD Pipeline
{Extract from root AGENTS.md ## CI/CD section}

| Field | Value |
|-------|-------|
| **Platform** | {From root AGENTS.md CI/CD} |
| **Repository** | {From root AGENTS.md CI/CD} |

#### Workflows

| Workflow | File | Trigger | Purpose |
|----------|------|---------|---------|
{Extract workflow table from root AGENTS.md CI/CD}

#### Deployment Flow

| Environment | Order | Trigger |
|-------------|-------|---------|
{Extract deployment environments from root AGENTS.md CI/CD}

#### Artifacts

| Artifact | Registry | Tags |
|----------|----------|------|
{Extract artifacts from root AGENTS.md CI/CD}

---

## 9. Testing & Quality Assurance

### 9.1 Test Project Inventory
| Component | Test Project | Type | Purpose |
|-----------|--------------|------|---------|
{Combine from all AGENTS.md ## Test Harness & Dev Tools > Test Projects}

### 9.2 E2E Test Integration

#### Test Selector Conventions
{Extract from entry point AGENTS.md ## Test Harness & Dev Tools > E2E Integration > Test Selectors}

| Element | Selector Pattern | Example |
|---------|------------------|---------|
{List standard data-testid conventions used}

#### Page Objects
| Page | File | Purpose |
|------|------|---------|
{Extract from entry point AGENTS.md ## Test Harness & Dev Tools > E2E Integration > Page Objects}

### 9.3 Test Utilities
| Utility | Location | Purpose |
|---------|----------|---------|
{Combine from all AGENTS.md ## Test Harness & Dev Tools > Test Utilities}

### 9.4 Test Data Setup
{Extract from AGENTS.md ## Test Harness & Dev Tools > Test Data Setup}

---

## 10. Appendices

### 10.1 Technology Stack Summary
| Component | Framework | Language |
|-----------|-----------|----------|
{Summarize from all entry points}

### 10.2 API Endpoint Reference
{Full list from all AGENTS.md API Exposed sections}

### 10.3 Glossary
{Key terms from all Key Concepts sections}
```

## Integration Diagram Template

Generate this Mermaid diagram showing system interactions (customize based on discovered components):

```mermaid
flowchart LR
    subgraph External
        EXT1[External Service 1]
        EXT2[External Service 2]
        AUTH[Auth Provider]
        STORE_SVC[Store Data Source<br/>Sites API / Store Service]
    end
    
    subgraph {Application Name}
        FE[Frontend]
        API[API Backend]
        DB[(Database)]
        QUEUE[Queue/Messaging]
    end
    
    FE -->|REST API| API
    API -->|SDK| DB
    API -->|Enqueue| QUEUE
    API -->|HTTP| EXT1
    API -->|HTTP| EXT2
    API -->|"Store Data"| STORE_SVC
    FE -->|SSO| AUTH
```

## Output Location

Write the complete PRD to:
```
/Documentation/prd-{application-name-lowercase}-generated.md
```

## Post-Generation Report

After generating the PRD, report:
1. Which AGENTS.md files were read
2. Which sections were populated from which source
3. Any sections that couldn't be populated (marked as TBD)
4. Any conflicts or inconsistencies detected between sources

---

## Maintenance Notes

- Run this generator whenever AGENTS.md files are updated
- The generated PRD should NOT be manually edited (it will be overwritten)
- If content is missing from generated PRD, update the source AGENTS.md file
- Keep AGENTS.md files as the source of truth
```

---

## Usage Instructions

When creating a new PRD generator for a repository:

1. Copy the template above to `{SolutionRoot}/Documentation/prd-generator-prompt.md`
2. Replace `{Application Name}` with the actual application name
3. Update the **Input Files** section with actual AGENTS.md file paths
4. Customize the Mermaid diagram based on the actual architecture
5. Adjust any sections specific to the application



