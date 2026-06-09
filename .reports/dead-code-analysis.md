# Dead Code Analysis Report

**Generated:** 2026-01-28
**Project:** Talk-to-Data
**Analysis Scope:** Frontend (TypeScript/React) + Backend (Python/FastAPI)

---

## Executive Summary

This report identifies unused dependencies, exports, and code across the project. The analysis found:
- **4 unused npm dependencies** in frontend
- **5 unused exports** in frontend
- **7 unused TypeScript types** in frontend
- **2 unused dev dependencies** in frontend

Total potential cleanup: **18 items**

---

## Frontend Analysis (TypeScript/React)

### 1. Unused Dependencies (SAFE to remove)

Found by: `depcheck` and `knip`

| Package | Type | Location | Safe to Remove |
|---------|------|----------|----------------|
| `eventsource-parser` | dependency | frontend/package.json:18 | ✅ YES |
| `markdown-it` | dependency | frontend/package.json:19 | ✅ YES |
| `highlight.js` | dependency | frontend/package.json:20 | ✅ YES |
| `sql.js` | dependency | frontend/package.json:21 | ✅ YES |
| `@types/markdown-it` | devDependency | frontend/package.json | ✅ YES |

**Risk Level:** SAFE
**Reasoning:** These packages are not imported anywhere in the frontend codebase.

### 2. Unused Exports (CAUTION - Review before removal)

Found by: `knip`

| Export | Location | Risk Level | Recommendation |
|--------|----------|------------|----------------|
| `sessionApi` | src/api/chat.ts:180, src/api/index.ts:1 | MEDIUM | May be intended for future use |
| `healthApi` | src/api/chat.ts:222, src/api/index.ts:1 | MEDIUM | May be intended for future use |
| `client` | src/api/index.ts:2 | LOW | Internal implementation detail |

**Risk Level:** CAUTION
**Reasoning:** These are exported but not used. However:
- `sessionApi` and `healthApi` appear to be API endpoints that may be planned
- `client` is an internal implementation detail

### 3. Unused TypeScript Types (SAFE to remove)

Found by: `ts-prune` and `knip`

| Type | Location | Used in Module? | Safe to Remove |
|------|----------|-----------------|----------------|
| `DataQueryResult` | src/types/index.ts:15 | Yes only in module | ⚠️ REVIEW |
| `SupervisorToolCall` | src/types/index.ts:45 | Yes only in module | ⚠️ REVIEW |
| `SSEEvent` | src/types/index.ts:140 | Yes only in module | ⚠️ REVIEW |
| `StreamStartEvent` | src/types/index.ts:147 | Yes only in module | ⚠️ REVIEW |
| `StreamProgressEvent` | src/types/index.ts:154 | Yes only in module | ⚠️ REVIEW |
| `StreamCompleteEvent` | src/types/index.ts:159 | Yes only in module | ⚠️ REVIEW |
| `StreamErrorEvent` | src/types/index.ts:164 | Yes only in module | ⚠️ REVIEW |

**Risk Level:** CAUTION
**Reasoning:** These types are exported but only used within their own module. They may be part of a public API.

---

## Backend Analysis (Python/FastAPI)

### Python Code Analysis

The Python backend was manually analyzed. Key findings:

1. **No automated tools available** - No `pylint`, `flake8`, or `autoflake` installed
2. **Manual code review shows:**
   - Main entry point: `app/main.py` - well structured
   - API router: `app/api/chat.py` - active use of all imports
   - No obviously unused imports detected in main files

**Recommendation:** Consider adding Python linting tools:
```bash
pip install pylint flake8 autoflake
```

---

## Severity Classification

### 🟢 SAFE (Immediate Cleanup)

These items are safe to remove immediately:

**Dependencies:**
- `eventsource-parser` - Not used
- `markdown-it` - Not used
- `highlight.js` - Not used
- `sql.js` - Not used
- `@types/markdown-it` - Not used

### 🟡 CAUTION (Review Required)

These items should be reviewed before removal:

**Exports:**
- `sessionApi` (src/api/chat.ts, src/api/index.ts) - May be planned API
- `healthApi` (src/api/chat.ts, src/api/index.ts) - May be planned API

**Types:**
- Stream event types (SSEEvent, StreamStartEvent, etc.) - Used in module but may be part of public API
- DataQueryResult, SupervisorToolCall - Used in module but may be part of public API

### 🔴 DANGER (Do Not Remove)

No items classified as DANGER in this analysis.

---

## Recommended Actions

### Phase 1: Safe Cleanup (Run Tests First)

1. **Verify tests pass:**
   ```bash
   cd frontend && npm test
   ```

2. **Remove unused dependencies:**
   ```bash
   cd frontend
   npm uninstall eventsource-parser markdown-it highlight.js sql.js
   npm uninstall -D @types/markdown-it
   ```

3. **Re-run tests:**
   ```bash
   npm test
   ```

4. **If tests fail:** Restore package.json and investigate

### Phase 2: Review Exports (Manual Review)

1. **Check if exports are intended for public API:**
   - Review API documentation
   - Check if any external consumers use these exports

2. **If safe to remove:**
   - Remove from `src/api/index.ts`
   - Remove from `src/api/chat.ts`
   - Run tests again

### Phase 3: Review Types (Manual Review)

1. **Check if types are part of public API:**
   - Review type definitions
   - Check if they should be exported for consumers

2. **If safe to remove:**
   - Remove export keyword
   - Keep type definition if used internally
   - Run tests

---

## Cleanup Summary

### Immediately Removable

- **4 dependencies** (frontend)
- **1 dev dependency** (frontend)
- **Total:** 5 packages

### Requires Manual Review

- **5 exports** (frontend API)
- **7 types** (frontend types)
- **Total:** 12 code items

### Files to Modify

1. `frontend/package.json` - Remove unused dependencies
2. `frontend/src/api/index.ts` - Review and potentially remove exports
3. `frontend/src/api/chat.ts` - Review and potentially remove exports
4. `frontend/src/types/index.ts` - Review and potentially remove type exports

---

## Tool Output

### Knip Output
```
Unused dependencies (4)
eventsource-parser  package.json:18:6
markdown-it         package.json:19:6
highlight.js        package.json:20:6
sql.js              package.json:21:6

Unused exports (5)
sessionApi  src/api/chat.ts:180:14
healthApi   src/api/chat.ts:222:14
sessionApi  src/api/index.ts:1:19
healthApi   src/api/index.ts:1:31
client      src/api/index.ts:2:21

Unused exported types (7)
DataQueryResult      interface  src/types/index.ts:15:18
SupervisorToolCall   interface  src/types/index.ts:45:18
SSEEvent             interface  src/types/index.ts:140:18
StreamStartEvent     interface  src/types/index.ts:147:18
StreamProgressEvent  interface  src/types/index.ts:154:18
StreamCompleteEvent  interface  src/types/index.ts:159:18
StreamErrorEvent     interface  src/types/index.ts:164:18
```

### Depcheck Output
```
Unused dependencies
* eventsource-parser
* markdown-it
* highlight.js
* sql.js
Unused devDependencies
* @types/markdown-it
```

### ts-prune Output
```
\src\api\index.ts:1 - chatApi
\src\api\index.ts:1 - sessionApi
\src\api\index.ts:1 - healthApi
\src\api\index.ts:2 - client
\src\router\index.ts:21 - default
\src\stores\index.ts:1 - useChatStore
\src\types\index.ts:3 - ChatRequest
[... and many more types ...]
```

---

## Next Steps

1. ✅ Review this report
2. ⏳ Verify test suite exists and passes
3. ⏳ Remove SAFE items (Phase 1)
4. ⏳ Review CAUTION items (Phase 2-3)
5. ⏳ Update documentation if needed
6. ⏳ Commit changes with descriptive message

---

**Report End**
