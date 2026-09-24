# Update AGENTS.md Files

Based on the changes made, update relevant AGENTS.md files.

**Reference:** Templates and required fields are defined in `templates/agents-md-templates.md`

---

## When to Update

| Change Type | Update Location | Template Section |
|-------------|-----------------|------------------|
| New API endpoint | Entry point's AGENTS.md (add to endpoint table) | External Interfaces > APIs Exposed |
| New service/class | Entry point's AGENTS.md (add to patterns section) | Key Patterns |
| New entity/model | Entry point's AGENTS.md (add to data/models section) | Data Contracts |
| New UI feature | Frontend entry point's AGENTS.md | Features list |
| Architecture change | Root AGENTS.md | Architecture section |
| New entry point project | Root AGENTS.md (add to index) + create entry point AGENTS.md | Entry Point Index |
| New class library | Root AGENTS.md (add to Supporting Libraries table) | Supporting Libraries |
| **New test harness/dev tool** | Entry point's AGENTS.md | Test Harness & Dev Tools |
| **Test harness enhancement** | Entry point's AGENTS.md (update harness section) | Test Harness & Dev Tools |
| **E2E test integration** | Entry point's AGENTS.md (add test selectors) | Test Harness > E2E Integration |
| **Store data source change** | Root AGENTS.md (update store data scope section) | Store Data Scope |
| **Store inclusion/exclusion change** | Root AGENTS.md (update filtering rules) | Store Data Scope |

---

## Key Principle

**Document class libraries within their parent entry point's AGENTS.md**, not in separate files.

For example, if you add a new service in `MyApp.Services`:
- ✅ Update `MyApp.Api/AGENTS.md` (the entry point that uses it)
- ❌ Don't create `MyApp.Services/AGENTS.md`

---

## Update Guidelines

1. **Follow template structure** - Use the section formats from `templates/agents-md-templates.md`
2. **Be concise** - Match the existing documentation style
3. **Add to existing tables** - Don't create new sections unless necessary
4. **Document patterns** - If introducing a new pattern, document it
5. **Update examples** - If behavior changed, update code examples

---

## Documentation Checklist

- [ ] New endpoints documented in APIs Exposed table
- [ ] New services/classes documented in Key Patterns
- [ ] New entities documented in Data Contracts
- [ ] Architecture changes reflected in diagrams
- [ ] Supporting libraries table updated (if new library added)
- [ ] Store data scope updated (if store filtering logic, data source, or inclusion/exclusion rules changed)

---

## Developer Approval

**Present proposed documentation changes to the developer for approval before proceeding to Generate PRD.**

