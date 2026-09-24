---
name: prd-regenerate
description: Regenerate the unified PRD from existing AGENTS.md files
---

# PRD regenerate

This command regenerates the unified PRD document from all AGENTS.md files in the repository.

**Use this command when:**
- AGENTS.md files have been updated
- New entry points have been added
- You need to refresh the PRD with current documentation

---

## Instructions

### Step 1: Locate PRD Generator

First, look for `**/prd-generator-prompt.md`.

If found, read it to understand the specific configuration for this repository.

### Step 2: Discover AGENTS.md Files

Find all `**/AGENTS.md` files in the repository.

### Step 3: Read All AGENTS.md Files

Read each AGENTS.md file to extract:
- **Root AGENTS.md**: System identity, organizational metadata, architecture overview, database configuration, CI/CD, store data scope
- **Entry Point AGENTS.md files**: Component details, features, technical stack, external services consumed, store data scope overrides (if any)

### Step 3a: Verify Database Information (Optional - Key Vault)

**If the Database section in AGENTS.md is missing server locations or needs verification:**

You can attempt to pull database connection information from Azure Key Vault if access is available.

> ⚠️ **CRITICAL SECURITY WARNING:**
> 
> When extracting database information from Key Vault or connection strings:
> - ✅ **ONLY extract:** Server names, Database names
> - ❌ **NEVER extract or display:** Passwords, User IDs, credentials, authentication tokens
> - ❌ **NEVER output:** Full connection strings or any credential-containing values
> 
> **All commands below are designed to extract ONLY server and database names.**

```text
az account show --query name -o tsv
az keyvault list --query "[].name" -o tsv
az keyvault secret list --vault-name {vault-name} --query "[?contains(name, 'Connection') || contains(name, 'Sql') || contains(name, 'Database')].name" -o tsv
```

If `az account show` fails, run `az login`. Fetch each secret **into a shell variable**, parse, and print **only** server and database names. Never run `az keyvault secret show ... -o tsv` as a standalone command. Run **only** the fence for the current shell:

```powershell
$secret = az keyvault secret show --vault-name {vault-name} --name {secret-name} --query "value" -o tsv
$server = ''
$db = ''
if ($secret -match 'Server=tcp:([^,;]+)') { $server = $Matches[1] }
elseif ($secret -match 'Data Source=([^;]+)') { $server = $Matches[1] }
if ($secret -match 'Initial Catalog=([^;]+)') { $db = $Matches[1] }
elseif ($secret -match 'Database=([^;]+)') { $db = $Matches[1] }
$secret = $null
Write-Output $server
Write-Output $db
```

```bash
SECRET_VALUE=$(az keyvault secret show --vault-name {vault-name} --name {secret-name} --query "value" -o tsv)
SERVER=$(printf '%s\n' "$SECRET_VALUE" | sed -n 's/.*Server=tcp:\([^,;]*\).*/\1/p' | sed -n '1p')
if [ -z "$SERVER" ]; then
  SERVER=$(printf '%s\n' "$SECRET_VALUE" | sed -n 's/.*Data Source=\([^;]*\).*/\1/p' | sed -n '1p')
fi
DATABASE=$(printf '%s\n' "$SECRET_VALUE" | sed -n 's/.*Initial Catalog=\([^;]*\).*/\1/p' | sed -n '1p')
if [ -z "$DATABASE" ]; then
  DATABASE=$(printf '%s\n' "$SECRET_VALUE" | sed -n 's/.*Database=\([^;]*\).*/\1/p' | sed -n '1p')
fi
unset SECRET_VALUE
printf '%s\n' "$SERVER"
printf '%s\n' "$DATABASE"
```

# ❌ NEVER DO THIS - Do not store or output the full connection string:
# BAD: az keyvault secret show ... --query "value" -o tsv
# BAD: echo "$SECRET_VALUE"

**Note:** This step is optional and only needed if AGENTS.md database information is incomplete. Skip if database details are already documented. **Only server names and database names should ever be documented - never credentials.**

### Step 4: Generate PRD Sections

Create or update the PRD document with these sections:

1. **System Identity** - Application name, description, URLs, ownership, business impact
2. **Technical Architecture** - System overview, architecture diagram, tech stack summary
3. **Component Details** - Each entry point with features, stack, patterns
4. **External Interfaces** - API endpoints, SignalR hubs, Service Bus, queues, external services consumed
5. **Data Architecture** - Database configuration (type, name, servers per environment), storage, data flows, data classification, store data scope
6. **Security & Compliance** - Authentication, authorization, secrets, compliance
7. **Deployment & Infrastructure** - Hosting, environment URLs, CI/CD
8. **Development Guidelines** - Ports, prerequisites, common commands
9. **Test Harness & Dev Tools** - Developer tools, test panels, E2E test integration (if applicable)
10. **Appendices** - File index, related resources, TBD items

### Step 5: Generate Architecture Diagram

Create a Mermaid flowchart showing:
- Client applications
- Compute services (APIs, Functions, App Services)
- Data storage (SQL Server, Cosmos DB, Access DB, blob storage, queues - with server names if documented)
- Store data sources (Sites API, Azure Store Service, KTServiceLibrary - if applicable)
- Messaging (SignalR, Service Bus)
- Security (Key Vault, App Insights)
- Identity providers
- On-premise components (if any)

### Step 6: Write PRD

Save the generated PRD to:
- `Documentation/prd-{application-name-lowercase}-generated.md`

If the Documentation folder doesn't exist, create it.

### Step 7: Report Completion

Present a summary:

> "✅ **PRD Regenerated**
> 
> **Output:** `Documentation/prd-{name}-generated.md`
> 
> **Sources:** {count} AGENTS.md files
> 
> **Sections Updated:**
> - System Identity ✅
> - Technical Architecture ✅
> - Component Details ✅
> - External Interfaces ✅
> - Data Architecture ✅
> -   Store Data Scope ✅ (if applicable)
> - Security & Compliance ✅
> - Deployment & Infrastructure ✅
> - Development Guidelines ✅
> - Test Harness & Dev Tools ✅ (if applicable)
> - Appendices ✅
> 
> **TBD Items:** {list any fields marked TBD}"

---

## PRD Template Structure

```markdown
# {Application Name} - Product Requirements Document

**Generated:** {Date}
**Source:** AGENTS.md documentation files
**Version:** {Version}

---

## Table of Contents
1. System Identity
2. Technical Architecture
3. Component Details
4. External Interfaces
5. Data Architecture
6. Security & Compliance
7. Deployment & Infrastructure
8. Development Guidelines
9. Test Harness & Dev Tools
10. Appendices

---

## 1. System Identity
{Extract from root AGENTS.md}

## 2. Technical Architecture
{Synthesize architecture from all AGENTS.md files}
{Include Mermaid diagram}

## 3. Component Details
{One subsection per entry point}

## 4. External Interfaces
{API endpoints, messaging, real-time, external services consumed}

## 5. Data Architecture
{Database configuration, storage, data classification}

### 5.1 Database Configuration
| Field | Value |
|-------|-------|
| **Database Type** | {SQL Server / Cosmos DB / Access DB / None} |
| **Database Name** | {DatabaseName or N/A} |
| **ORM/Data Access** | {Entity Framework Core / Dapper / etc.} |

### 5.2 Server Locations
| Environment | Server | Notes |
|-------------|--------|-------|
| Dev | {server}.database.windows.net | {Azure SQL} |
| QA | {server}.database.windows.net | {Azure SQL} |
| Prod | {server}.database.windows.net | {Azure SQL} |

*Note: If Database Type is "None", replace with a note explaining data storage approach.*

### 5.3 Data Classification
{Sensitivity, data types}

### 5.4 Store Data Scope
{Extract from root AGENTS.md Store Data Scope section}

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

*Note: This section only appears if the root AGENTS.md contains a Store Data Scope section. If the application does not interact with store data, include a note indicating "Not Applicable".*

## 6. Security & Compliance
{Auth, authorization, secrets, compliance}

## 7. Deployment & Infrastructure
{Hosting, URLs, CI/CD}

## 8. Development Guidelines
{Ports, prerequisites, commands}

## 9. Test Harness & Dev Tools
{Extract from entry point AGENTS.md files with Test Harness sections}

### 9.1 Overview
{List all components with test harness functionality}

### 9.2 Test Panels
| Component | Route | Purpose | Visibility |
|-----------|-------|---------|------------|
| {ComponentName} | `/testPanel` | {Purpose description} | Dev/Debug mode |

### 9.3 Test Harness Features
{Detail key test harness capabilities}
- Offline Queue Harness: Seed invalid data for sync testing
- Time Testing: Manipulate business date calculations
- Metadata Settings: Toggle environment flags

### 9.4 E2E Test Integration
{Document test selectors for Playwright/E2E tests}
| Selector | Component | Purpose |
|----------|-----------|---------|
| `[data-test-id="seed-waste-queue"]` | {Component} | Seed test data |

*Note: This section only appears if entry point AGENTS.md files contain Test Harness documentation.*

## 10. Appendices
{File index, resources, TBD items}

---

*This PRD was auto-generated from AGENTS.md documentation files.*
```

---

## Quick Regenerate (Single Command)

If you just need to quickly regenerate the PRD without reviewing the process:

> "Regenerate the PRD by reading all AGENTS.md files in this repository and updating Documentation/prd-*-generated.md with current content. Preserve the existing structure and update all sections."

