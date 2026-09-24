# AGENTS.md Templates

This file contains centralized templates for AGENTS.md files. These templates are designed to be used by multiple workflows and ensure consistency across all repositories.

---

## Metadata Completeness Audit

Use this section to audit existing AGENTS.md files for required organizational metadata.

### Root AGENTS.md - 40 Required Fields

| # | Field | Category | Check |
|---|-------|----------|-------|
| 1 | Application Name | Identity | ☐ |
| 2 | Description | Identity | ☐ |
| 3 | URL | Identity | ☐ |
| 4 | Tech Owner | Ownership | ☐ |
| 5 | Business Owner | Ownership | ☐ |
| 6 | Department | Ownership | ☐ |
| 7 | Dev Team | Ownership | ☐ |
| 8 | Products/Platforms | Platform | ☐ |
| 9 | Features | Platform | ☐ |
| 10 | Framework | Technical | ☐ |
| 11 | Programming Language | Technical | ☐ |
| 12 | Hosting Location | Technical | ☐ |
| 13 | Infrastructure | Technical | ☐ |
| 14 | Source Control | Technical | ☐ |
| 15 | Access Type | Security | ☐ |
| 16 | Authentication | Security | ☐ |
| 17 | Authorization | Security | ☐ |
| 18 | Compliance Requirements | Security | ☐ |
| 19 | DAST | Security | ☐ |
| 20 | SAST | Security | ☐ |
| 21 | Security Controls | Security | ☐ |
| 22 | Secret Management | Security | ☐ |
| 23 | Data Sensitivity | Data | ☐ |
| 24 | Data Type | Data | ☐ |
| 25 | Users per Month | Business | ☐ |
| 26 | Revenue Impact | Business | ☐ |
| 27 | Criticality | Business | ☐ |
| 28 | External Services | Integration | ☐ |
| 29 | Database Type | Database | ☐ |
| 30 | Database Name | Database | ☐ |
| 31 | Database Servers | Database | ☐ |
| 32 | CI Platform | CI/CD | ☐ |
| 33 | CI Workflows | CI/CD | ☐ |
| 34 | CD Workflows | CI/CD | ☐ |
| 35 | Deployment Environments | CI/CD | ☐ |
| 36 | Artifacts | CI/CD | ☐ |
| 37 | Test Harness | Dev Tools | ☐ |
| 38 | Store Data Source(s) | Store Data | ☐ |
| 39 | Store Inclusion/Exclusion Rules | Store Data | ☐ |
| 40 | Environment Data Replication | Replication | ☐ |

### Entry Point AGENTS.md - 13 Required Sections

| # | Section | Check |
|---|---------|-------|
| 1 | Application Metadata (name, type, description) | ☐ |
| 2 | Features list | ☐ |
| 3 | Technical Stack (framework, language, libraries) | ☐ |
| 4 | Architecture (layers, related projects) | ☐ |
| 5 | Project Structure (folder purposes) | ☐ |
| 6 | Authentication & Authorization | ☐ |
| 7 | External Interfaces (APIs exposed/consumed) | ☐ |
| 8 | Data Contracts (key models) | ☐ |
| 9 | Key Patterns | ☐ |
| 10 | Common Tasks | ☐ |
| 11 | Local Development | ☐ |
| 12 | Test Harness & Dev Tools | ☐ |
| 13 | Deployment | ☐ |

### How to Use the Audit

1. **Open the existing AGENTS.md file**
2. **Check each field/section** against the checklists above
3. **Mark as complete** (☑) if the field exists and has a value
4. **Mark as missing** (☐) if the field is absent or empty
5. **Report missing fields** to determine what needs to be gathered

---

## Auto-Discovery Reference

Use this table to automatically discover metadata from the codebase before asking the developer.

### Fields That CAN Be Auto-Discovered

| Field | Discovery Method | Confidence |
|-------|------------------|------------|
| Application Name | `.sln` filename or root folder | ✅ High |
| Description | README.md first paragraph | 🔍 Medium |
| URL | `launchSettings.json`, `appsettings.json` | ✅ High |
| Framework | `<TargetFramework>` in `.csproj` | ✅ High |
| Programming Language | File extensions (`.cs`, `.ts`, `.py`) | ✅ High |
| Hosting Location | Azure configs, `host.json`, pipeline files | 🔍 Medium |
| Infrastructure | Package references, connection strings | ✅ High |
| Source Control | `.git` folder, pipeline files | ✅ High |
| Authentication | Okta/AD/Identity packages in `.csproj` | ✅ High |
| Authorization | `[Authorize]` attributes, policy configs | 🔍 Medium |
| Secret Management | Key Vault references, `IConfiguration` | ✅ High |
| Features | API endpoints, page routes, function names | 🔍 Medium |
| CI Platform | `.github/workflows/` or `azure-pipelines.yml` | ✅ High |
| CI Workflows | Workflow files with `pull_request` trigger | ✅ High |
| CD Workflows | Workflow files with `push: main` trigger | ✅ High |
| Deployment Environments | Environment names in deployment jobs | ✅ High |
| Artifacts | Docker registry, NuGet feed references | ✅ High |
| Database Type | EF Core, Cosmos SDK, Azure Table packages | ✅ High |
| Database Name | Connection strings, `appsettings.json`, **Key Vault** | ✅ High* |
| Database Servers | Connection strings, **Key Vault secrets** | ✅ High* |
| Store Data Source(s) | `appsettings.json` store config keys, HttpClient registrations for Sites API / Azure Store Service / KTServiceLibrary | 🔍 Medium |
| Store Inclusion/Exclusion Rules | Env vars (`StoreNumbers`, `ExcludedStoreNumbers`), config keys (`IncludedRegions`, `ExcludedZones`, `IncludedDistricts`, `ExcludedDistricts`), filtering logic in code | 🔍 Medium |
| Environment Data Replication | `ProductionDataRefresh`, `DataRefreshOrchestrator`, `/environmentdatarefresh`, `HasDataReplicationFromProduction` in code/config | 🔍 Medium |

*\*High confidence when Key Vault access is available; otherwise ask developer.*

> ⚠️ **CRITICAL SECURITY WARNING - Database Discovery:**
> 
> When extracting database information from Key Vault or connection strings:
> - ✅ **ONLY extract:** Server names (`Server=`, `Data Source=`), Database names (`Initial Catalog=`, `Database=`)
> - ❌ **NEVER extract or display:** Passwords (`Password=`), User IDs (`User ID=`), credentials, authentication tokens
> - ❌ **NEVER output or store:** Full connection strings or any credential-containing values

### IoT Team Defaults

**These fields have organization-wide defaults for the team:**

| Field | Default Value | Notes |
|-------|---------------|-------|
| **Tech Owner** | `IoT` | Override if different team |
| **Dev Team** | `IoT` | Override if different team |
| **Source Control** | `GitHub` | Override if using Azure DevOps |

### Fields That CANNOT Be Auto-Discovered (Always Ask)

| Field | Reason | Has Default? |
|-------|--------|--------------|
| Tech Owner | Organizational knowledge | ✅ `IoT` |
| Business Owner | Organizational knowledge | ❌ |
| Department | Organizational knowledge | ❌ |
| Dev Team | Organizational knowledge | ✅ `IoT` |
| Products/Platforms | Business context | ❌ |
| Compliance Requirements | Legal/compliance context | ❌ |
| DAST | Process knowledge | ❌ |
| SAST | Process knowledge | ❌ |
| Security Controls | Infrastructure knowledge | ❌ |
| Data Sensitivity | Classification policy | ❌ |
| Data Type | Business context | ❌ |
| Database Servers | *Can be discovered from Key Vault if access available* | ⚠️ Conditional |
| Users per Month | Business metrics | ❌ |
| Revenue Impact | Business context | ❌ |
| Criticality | Business judgment | ❌ |

### Fields That Must NEVER Be Discovered or Documented

> ⚠️ **CRITICAL SECURITY - PROHIBITED FIELDS:**

| Field | Reason | Status |
|-------|--------|--------|
| **Database Passwords** | Credential security | 🚫 NEVER |
| **Database User IDs** | Credential security | 🚫 NEVER |
| **Full Connection Strings** | Contains credentials | 🚫 NEVER |
| **API Keys/Secrets** | Credential security | 🚫 NEVER |
| **Authentication Tokens** | Credential security | 🚫 NEVER |

These values must **never** be extracted, stored, displayed, or documented in AGENTS.md files or PRDs.

### Discovery reference (goals — do not shell `find`/`grep`)

| Goal | Pattern / extract |
|------|-------------------|
| Solution name | `**/*.sln` |
| Target framework | `<TargetFramework>` in `*.csproj` |
| Authentication | `Okta`, `Azure.Identity`, `IdentityServer` in `*.csproj`; `[Authorize` in `*.cs` |
| Infrastructure | `KeyVault`, `Cosmos`, `ServiceBus`, `SignalR` in `*.csproj` / `*.json` |
| API endpoints | `[HttpGet`, `[HttpPost`, `.MapGet`, `Function(` in `*.cs` |
| Blazor pages | `@page` in `*.razor` |
| External HTTP | `HttpClient`, `IHttpClientFactory` in `*.cs` |
| Database (code) | EF/Cosmos/Table packages in `*.csproj`; `DbContext`; `ConnectionStrings` in `*.json`; `UseSqlServer` / `UseCosmos` |
| Key Vault names | `KeyVault`, `VaultUri`, `vault.azure.net` in `*.json` / `*.cs` |
| Key Vault secrets | Dual-shell parse (secret stays in a variable). Print only server/database. Never standalone `az keyvault secret show -o tsv` |
| Store scope | `StoreNumber`, `SitesApi`, include/exclude lists, `AzureStoreService`, `Region`/`District` |
| Replication | `EnvironmentDataRefresh`, `ProductionDataRefresh`, `DataRefreshOrchestrator` |
| Local URLs | `applicationUrl` in `**/Properties/launchSettings.json` |
| CI/CD | `.github/workflows/*.{yml,yaml}` — `pull_request`, `push:` to `main`/`master`, `environment`, docker, nuget |

Database from Key Vault: `az login` first. Extract **only** `Server=tcp:` / `Data Source=` and `Initial Catalog=` / `Database=`. Never document credentials or full connection strings.

---

## Entry Point Project Types

Use this table to identify which projects should have AGENTS.md files:

| Project Type | Pattern Examples | Gets AGENTS.md |
|--------------|------------------|----------------|
| **API/Backend** | `*.Api`, `*.Functions`, `*.Web.Api`, `*.Http.*` | ✅ Yes |
| **Frontend UI** | `*.PWA`, `*.Admin`, `*.Web`, `*.Blazor`, `*.UI` | ✅ Yes |
| **Worker/Service** | `*.Worker`, `*.Jobs`, `*.Processor`, `*.Listener` | ✅ Yes |
| **Console App** | `*.Console`, `*.CLI` | ✅ Yes |
| Class Library | `*.Models`, `*.Data`, `*.Services`, `*.Common`, `*.Shared`, `*.Client` | ❌ No |
| Tests | `*.Tests`, `*.UnitTests`, `*.E2E.Tests` | ❌ No |

---

## Root AGENTS.md Template

**Location:** `{SolutionRoot}/AGENTS.md`

**Required:** Every root file must include `## Environment Data Replication` (full section below, or the Not Applicable single-table stub). The documentation workflow discovers this in Step 3a-REPLICATION; PRD §4.5 extraction and Step 7b validation fail if the heading is absent.

```markdown
# AGENTS.md

This repository uses AGENTS.md files as the authoritative guidance for LLM agents.

---

## Application Metadata

| Field | Value |
|-------|-------|
| **Application Name** | {Application Name} |
| **Description** | {Short description of what the application does} |
| **URL** | {Application URL - or note if console app/service/API} |

### Ownership

| Field | Value |
|-------|-------|
| **Tech Owner** | {Dev team: MC, Credit, IoT, Retail, etc.} |
| **Business Owner** | {Business side owner} |
| **Department** | {Department this application supports} |
| **Dev Team** | {Development team name} |

### Products & Platforms

| Field | Value |
|-------|-------|
| **Products/Platforms** | {AMS, Sales Force, Maximo, etc.} |
| **Features** | {What the app does: sends email, transfers data, updates records, etc.} |

---

## Technical Stack

### Frameworks & Languages

| Field | Value |
|-------|-------|
| **Framework** | {.NET Core, React.js, Blazor, etc.} |
| **Programming Language** | {C#, Python, TypeScript, etc.} |

### Infrastructure

| Field | Value |
|-------|-------|
| **Hosting Location** | {Azure / On-Prem / Hybrid} |
| **Infrastructure** | {List of Azure resources or internal servers} |
| **Source Control** | {GitHub / Azure DevOps} |

---

## Security & Compliance

### Authentication & Access

| Field | Value |
|-------|-------|
| **Access Type** | {Private / Public} |
| **Authentication** | {IDS, Okta, AD, Access Keys, etc.} |
| **Authorization** | {Role-based, Claims-based, etc.} |

### Compliance

| Field | Value |
|-------|-------|
| **Compliance Requirements** | {PCI, HIPAA, SOX, None, etc.} |
| **Security Assessment - DAST** | {Yes/No - Dynamic Code Scanning} |
| **Security Assessment - SAST** | {Yes/No - Static Code Scanning} |
| **Security Controls** | {WAF, Firewall, etc.} |

### Secret Management

| Field | Value |
|-------|-------|
| **Secret Management** | {Azure Key Vault, GitHub Secrets, appsettings, etc.} |

---

## Data Classification

| Field | Value |
|-------|-------|
| **Data Sensitivity** | {Public / Internal / Confidential / Restricted} |
| **Data Type** | {Financial records, sales, proprietary, PII, etc.} |

---

## Database

| Field | Value |
|-------|-------|
| **Database Type** | {SQL Server / Cosmos DB / Azure Table Storage / PostgreSQL / Access DB / None} |
| **Database Name** | {DatabaseName or N/A} |
| **ORM/Data Access** | {Entity Framework Core / Dapper / Cosmos SDK / None} |
| **Connection Pattern** | {Azure Key Vault / Direct Connection String / Managed Identity} |

### Server Locations

| Environment | Server Name | Notes |
|-------------|-------------|-------|
| **Dev** | `{dev-server}.database.windows.net` | {Azure SQL / Cosmos endpoint / etc.} |
| **QA** | `{qa-server}.database.windows.net` | {Azure SQL / Cosmos endpoint / etc.} |
| **Prod** | `{prod-server}.database.windows.net` | {Azure SQL / Cosmos endpoint / etc.} |

*Note: If this application does not use a database, set Database Type to "None" and remove the Server Locations and Connection Configuration sections.*

---

## Store Data Scope

### Store Data Source(s)

| Source | Usage | Config Key |
|--------|-------|------------|
| {Sites API / Azure Store Service / KTServiceLibrary / Direct DB / None} | {Primary store list, filtering, validation, etc.} | `{ConfigKey or N/A}` |

### Store Inclusion Rules

| Rule Type | Value | Mechanism |
|-----------|-------|-----------|
| {All Stores / Specific Stores / By Region / By Zone / By District / By Site Type / Other} | {values or "All"} | {Env Variable / App Config / Database / Hardcoded / N/A} |

### Store Exclusion Rules

| Rule Type | Value | Mechanism |
|-----------|-------|-----------|
| {Region / Zone / Food Service District / District / Store Number / Site Type Code / Store Status / None} | {values or "None"} | {Env Variable / App Config / Database / Runtime Logic / N/A} |

*Note: If this application does not interact with store-specific data, replace the subsections above with:*

| Field | Value |
|-------|-------|
| **Store Data** | Not Applicable - This application does not interact with store-specific data |

---

## Environment Data Replication

Canonical documentation for copying production reference data into non-production environments (and any follow-on regeneration). User-facing name in UI/PRD is often **Environment Data Refresh** — cross-reference entry-point `## User Workflows` subsections when present.

### Purpose & Scope

| Aspect | Detail |
|--------|--------|
| **Purpose** | {What production reference data is copied and why} |
| **Environments** | Non-production only (e.g., Development, QA). Production never receives replication |
| **Scheduling** | {Manual Admin trigger / API-only / Not applicable} |
| **Not replicated** | {Entities intentionally excluded — e.g., transactional instances, device data} |

### Trigger & Access Control

| Control | Detail |
|---------|--------|
| **Admin UI** | {Route e.g. `/environmentdatarefresh` — or N/A} |
| **Start API** | {e.g. `POST /api/v1/ProductionDataRefresh` — or N/A} |
| **Status API** | {e.g. `GET /api/v1/ProductionDataRefresh/status` — or N/A} |
| **Concurrency** | {Single-run guard — or N/A} |
| **Client apps** | {How non-admin clients reconcile after refresh — or N/A} |

### Orchestration Stages

{Durable orchestration / pipeline name} runs these stages in order:

| Stage | Description |
|-------|-------------|
| **{Stage1}** | {e.g., copy production reference entities into target environment storage} |
| **{Stage2}** | {e.g., delete existing derived instances} |
| **{Stage3}** | {e.g., regenerate instances for active stores} |
| **Completed** / **Failed** | Final status persisted; notifications sent when configured |

### Replicated Production Data

Replication reads from production (when gated) and upserts into the target environment in this order:

| Order | Storage Entity | Content |
|-------|----------------|---------|
| 1 | `{Entity1}` | {Description} |
| 2 | `{Entity2}` | {Description} |
| 3 | `{Entity3}` | {Description} |
| 4 | `{Entity4}` | {Description} |
| 5 | `{Entity5}` | {Description} |
| 6 | `{Entity6}` | {Description} |
| 7 | `{Entity7}` | {Description} |
| 8 | `{Entity8}` | {Description} |

{Document entities that are deleted/regenerated rather than copied.}

### Configuration Gates

Replication is disabled unless all gates pass. Document config **key names only** — values live in Key Vault or environment secrets.

| Setting | Purpose |
|---------|---------|
| `{MasterReplicationGate}` | Master gate — when disabled, refresh API returns error |
| `{ProductionSourceEndpoint}` | Production read-only source endpoint |
| `{ProductionSourceAuth}` | Production source auth secret/key name |
| `{ProductionSourceDatabase}` | Production source database/account ID |
| `{TargetEndpoint}` | Target environment endpoint — must differ from production when replication enabled |
| `{AdditionalGate1}` | {Purpose} |
| `{NotificationUrl}` | Outcome notification endpoint (if applicable) |
| `{NotificationRecipients}` | Distribution list config key (if applicable) |

### Status & History

| Item | Detail |
|------|--------|
| **History store** | {Container/table name and partition key — or N/A} |
| **Status model** | {Fields tracked — current stage, timestamps, last error} |
| **Admin polling** | {Polling interval while in progress vs idle — or N/A} |

### Notifications

{How success/failure is notified — e.g., external email function, webhook — or "None"}

### Component References

| Component | Documentation |
|-----------|---------------|
| **Admin trigger & UI** | `{AdminProject}/AGENTS.md` — {subsection name} |
| **API orchestration** | `{ApiProject}/AGENTS.md` — {subsection name} |
| **Client impact** | `{ClientProject}/AGENTS.md` — {subsection name} |

*Note: If this application does not implement environment data replication, replace the subsections above with:*

| Field | Value |
|-------|-------|
| **Environment Data Replication** | Not Applicable — This application does not copy production reference data into non-production environments |

---

## Business Impact

| Field | Value |
|-------|-------|
| **Number of Users per Month** | {Approximate user count} |
| **Revenue Impact** | {Impact if application breaks/unavailable} |
| **Criticality** | {Critical / High / Medium / Low} |

---

## CI/CD

| Field | Value |
|-------|-------|
| **Platform** | {GitHub Actions / Azure DevOps} |
| **Repository** | {org/repo-name} |

### Workflows

| Workflow | File | Trigger | Purpose |
|----------|------|---------|---------|
| **CI** | `{ci-workflow}.yml` | `pull_request` | Build, Test, Security Scan |
| **CD** | `{cd-workflow}.yml` | `push: main` | Build, Publish, Deploy |
| **Continuous Scanning** | `{cs-workflow}.yml` | `schedule` (cron) | CodeQL, Vulnerability Scan |

### CI Pipeline (Pull Requests)

| Step | Description |
|------|-------------|
| **Build** | {Compile solution, restore packages} |
| **Test** | {Run unit/integration tests} |
| **Docker Build** | {Build container image - not pushed} |
| **Security Scan** | {Scan for vulnerabilities} |

### CD Pipeline (Merge to Main)

| Step | Description |
|------|-------------|
| **Version** | {Version numbering strategy} |
| **Docker Publish** | {Push to container registry} |
| **NuGet Publish** | {Pack and push packages - if applicable} |
| **Deploy** | {Deployment strategy: sequential/parallel} |

### Deployment Environments

| Environment | Order | Runner Group | Trigger |
|-------------|-------|--------------|---------|
| **dev** | 1st | {runner-group} | Automatic on merge |
| **qa** | 2nd | {runner-group} | After dev succeeds |
| **prod** | 3rd | {runner-group} | After qa succeeds |

### Artifacts

| Artifact | Registry/Location | Tags |
|----------|-------------------|------|
| **Docker Image** | `{registry/org/image-name}` | `latest`, `{version}` |
| **NuGet Packages** | `{nuget-feed-name}` | {package names} |

### Required Secrets

| Secret | Purpose | Scope |
|--------|---------|-------|
| `AZURE_CLIENT_ID` | Azure deployment auth | Environment |
| `AZURE_CLIENT_SECRET` | Azure deployment auth | Environment |
| `AZURE_TENANT_ID` | Azure AD tenant | Organization |
| `AZURE_SUBSCRIPTION_ID` | Target subscription | Environment |

---

## System Overview

{Brief description of what the system does and its purpose}

### Architecture

{Describe the high-level architecture - entry points, supporting libraries, how they interact}

### Key Concepts

{List important business concepts and domain terminology}

---

## Entry Point Index

| Entry Point | File | Description |
|-------------|------|-------------|
| {ApiProject} | `{ApiProject}/AGENTS.md` | Backend API - {brief description} |
| {WebProject} | `{WebProject}/AGENTS.md` | Frontend UI - {brief description} |

## Supporting Libraries

| Library | Purpose |
|---------|---------|
| {Project}.Models | Domain models shared across layers |
| {Project}.Services | Business logic layer |
| {Project}.Data | Data access layer |

---

## Quick Reference

### Development Ports

| Component | Port |
|-----------|------|
| API | {port} |
| Frontend | {port} |

### Development Commands

```bash
# Restore dependencies
dotnet restore

# Build solution
dotnet build

# Run tests
dotnet test
```

---

## Policy

- Use AGENTS.md files as the authoritative source for project guidance
- Prefer local development settings files (never change shared/non-local settings)
- Keep edits minimal and focused; update AGENTS.md when workflows or commands change
```

---

## Entry Point AGENTS.md Template

**Location:** `{ProjectFolder}/AGENTS.md`

```markdown
# AGENTS.md - {Entry Point Name}

This file provides guidance to LLM agents working with the {Entry Point Name} and its supporting libraries.

---

## Application Metadata

| Field | Value |
|-------|-------|
| **Component Name** | {Entry Point Name} |
| **Component Type** | {API / Frontend / Worker / Console} |
| **Description** | {What this component does} |
| **URL** | {Component-specific URL if applicable} |

### Features

{List the key features this component provides}

- Feature 1: {Description}
- Feature 2: {Description}
- Feature 3: {Description}

---

## Technical Stack

| Field | Value |
|-------|-------|
| **Framework** | {Blazor Server, Azure Functions, etc.} |
| **Language** | {C#, TypeScript, etc.} |
| **Key Libraries** | {MudBlazor, FluentValidation, etc.} |

---

## Architecture

This entry point uses the following layers/libraries:

| Layer | Project | Purpose |
|-------|---------|---------|
| API/UI | {This Project} | {Entry point description} |
| Services | {Services Project} | Business logic |
| Data | {Data Project} | Data access |
| Models | {Models Project} | Domain models |

---

## Project Structure

| Folder | Purpose |
|--------|---------|
| {Folder1}/ | {Description} |
| {Folder2}/ | {Description} |

---

## Authentication & Authorization

| Field | Value |
|-------|-------|
| **Auth Method** | {Okta, Azure AD, API Key, etc.} |
| **Auth Flow** | {OAuth2, OIDC, Basic, etc.} |
| **Required Roles** | {Admin, User, etc.} |

---

## External Interfaces

### APIs Exposed

| Endpoint | Method | Description |
|----------|--------|-------------|
| {/api/resource} | {GET/POST} | {Description} |

### APIs Consumed

| Service | Purpose |
|---------|---------|
| {External Service} | {What data/functionality it provides} |

### Store Data Scope (if different from root)

*Only include this section if this entry point applies store filtering different from or in addition to the root AGENTS.md Store Data Scope. Most entry points inherit the root's store data scope.*

| Field | Value |
|-------|-------|
| **Additional Filtering** | {Describe any component-specific store inclusion/exclusion logic, or "Inherits root Store Data Scope"} |

---

## Data Contracts

### Key Models

| Model | Purpose |
|-------|---------|
| {ModelName} | {Description} |

---

## Key Patterns

### {Pattern Name}

{Describe important patterns, conventions, or rules for this entry point and its layers}

---

## Common Tasks

### Adding a new {feature type}

1. {Step 1}
2. {Step 2}
3. {Step 3}

---

## Local Development

### Running Locally

```bash
# Navigate to project
cd {ProjectFolder}

# Run the application
dotnet run
```

### Configuration

| Setting | Description | Location |
|---------|-------------|----------|
| {SettingName} | {What it controls} | {appsettings.json, env var, etc.} |

---

## Test Harness & Dev Tools

### Test Projects

| Project | Type | Purpose |
|---------|------|---------|
| {Project}.Tests | Unit | Unit tests for business logic |
| {Project}.IntegrationTests | Integration | API/database integration tests |
| {Project}.E2E.Tests | E2E/Playwright | End-to-end UI tests |

### E2E Integration

#### Test Selectors

Use `data-testid` attributes for stable E2E test selectors:

| Element | Selector Pattern | Example |
|---------|------------------|---------|
| Buttons | `data-testid="{action}-btn"` | `data-testid="submit-btn"` |
| Forms | `data-testid="{name}-form"` | `data-testid="login-form"` |
| Inputs | `data-testid="{field}-input"` | `data-testid="email-input"` |
| Tables | `data-testid="{name}-table"` | `data-testid="users-table"` |
| Rows | `data-testid="{name}-row-{id}"` | `data-testid="user-row-123"` |

#### Page Objects

| Page | File | Purpose |
|------|------|---------|
| {PageName} | `{PageName}Page.cs` | {Description of page interactions} |

### Test Utilities

| Utility | Location | Purpose |
|---------|----------|---------|
| {UtilityName} | `{Path}` | {What it helps with} |

### Test Data Setup

{Describe how test data is created/seeded, any fixtures or factories used}

---

## Deployment

| Environment | URL | Notes |
|-------------|-----|-------|
| Development | {url} | {notes} |
| QA/Staging | {url} | {notes} |
| Production | {url} | {notes} |
```

---

## Required Fields Checklist

When creating AGENTS.md files, ensure these fields are populated:

### Root AGENTS.md Required Fields

- [ ] Application Name
- [ ] Description
- [ ] URL (or note application type)
- [ ] Tech Owner
- [ ] Business Owner
- [ ] Department
- [ ] Products/Platforms supported
- [ ] Features list
- [ ] Framework
- [ ] Programming Language
- [ ] Hosting Location
- [ ] Infrastructure resources
- [ ] Source Control
- [ ] Access Type (Private/Public)
- [ ] Authentication method
- [ ] Compliance Requirements
- [ ] DAST status
- [ ] SAST status
- [ ] Security Controls
- [ ] Secret Management approach
- [ ] Data Sensitivity level
- [ ] Data Type
- [ ] Database Type (or "None" if no database)
- [ ] Database Name (if applicable)
- [ ] Database Server Locations (if applicable)
- [ ] Number of users per month
- [ ] Revenue Impact
- [ ] Criticality level
- [ ] CI Platform
- [ ] CI Workflows
- [ ] CD Workflows
- [ ] Deployment Environments
- [ ] Artifacts
- [ ] Store Data Source(s) (or "None" if no store data)
- [ ] Store Inclusion Rules (or "All Stores")
- [ ] Store Exclusion Rules (or "None")
- [ ] Environment Data Replication (or "Not Applicable" with purpose/stages/entities omitted)

### Entry Point AGENTS.md Required Fields

- [ ] Component Name
- [ ] Component Type
- [ ] Description
- [ ] Features list
- [ ] Framework
- [ ] Key Libraries
- [ ] Architecture layers
- [ ] Project structure
- [ ] Authentication method
- [ ] APIs exposed (if applicable)
- [ ] APIs consumed
- [ ] Key data models
- [ ] Local development instructions
- [ ] Test projects (unit/integration/E2E)
- [ ] E2E test selectors (if UI project)
- [ ] Test utilities and data setup
- [ ] Deployment environments

