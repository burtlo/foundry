# Add Tests

Based on the changes made, add appropriate tests.

---

## Discover Test Projects

Find `*.csproj` files that reference `Microsoft.NET.Test.Sdk`, `xunit`, `NUnit`, `MSTest`, or `Playwright`.

---

## Identify Test Project Types

| Project Pattern | Test Type |
|-----------------|-----------|
| `*.Tests` or `*.UnitTests` | Unit Tests |
| `*.IntegrationTests` | Integration Tests |
| `*.E2E.Tests` or contains `Playwright` | E2E/Playwright Tests |

---

## For Each Type of Change, Add Appropriate Tests

### Unit Tests

For new/modified business logic:

```csharp
[Fact]
public async Task Subject_Scenario_ExpectedOutcome()
{
    // Arrange
    // Act
    // Assert
}
```

---

### Integration Tests

For API/endpoint changes:

```csharp
[Fact]
public async Task Endpoint_Scenario_ExpectedOutcome()
{
    // Test with mocked dependencies or test database
}
```

---

### E2E Playwright Tests

For user-facing UI changes:

```csharp
[Test]
public async Task UserFlow_Scenario_ExpectedOutcome()
{
    await Page.GotoAsync("https://localhost:{port}");
    // User interaction steps
    // Assertions
}
```

---

## Test Naming Convention

**Always** name tests `Subject_Scenario_ExpectedOutcome` (three underscore-separated parts).

| Component | Description | Examples |
|-----------|-------------|----------|
| **Subject** | Type, method, endpoint, or feature under test | `CommandReceiverType`, `GetCommandDefaultPayload`, `DeserializePackageString` |
| **Scenario** | Condition, input, or member being exercised | `Tines`, `DriivzReset`, `LegacyTinesIntegerValues` |
| **ExpectedOutcome** | Concrete expected result (verb phrase) | `EqualsTwo`, `ReturnsExpectedJson`, `MapToTinesMembers` |

```csharp
// ✅ Good — Subject_Scenario_ExpectedOutcome
public void CommandReceiverType_Tines_EqualsTwo()
public void GetCommandDefaultPayload_DriivzReset_ReturnsExpectedJson()
public void DeserializePackageString_LegacyTinesIntegerValues_MapToTinesMembers()

// ❌ Avoid — vague, missing segments, or not matching project style
public void ActionCommandReceiverType_TinesRetainsPreDriivzIntegerValue()
public void TestTinesEnum()
```

### Before adding tests

1. **Read existing tests** in the target test project and match local naming style.
2. Prefer **one assertion per test** when verifying independent facts (e.g. each enum integer value gets its own test).
3. Multi-step user flows (E2E) may keep related assertions in one test when they describe a single outcome.

---

## Proceed to Run Tests

After adding tests, proceed to Run Tests to execute all tests.

