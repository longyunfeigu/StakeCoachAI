# Multi-Persona Defense Prep Design

## Overview

Support selecting multiple personas (up to 5) as defense reviewers. Each persona independently generates questions based on their role/style, and questions are interleaved by dimension during the simulated defense session.

## Design Decisions

- **Collaboration mode**: Round-robin questioning — each persona asks from their own perspective, interleaved by dimension (not sequential per persona)
- **Max personas**: 5
- **Question count**: `max(3, 12 // n)` per persona, total ~12
- **Backward compatibility**: Migrate existing `persona_id` to `persona_ids` JSON array

## Data Layer

### DB Migration

```sql
-- Rename persona_id → persona_ids, change type to JSON
ALTER TABLE defense_sessions DROP COLUMN persona_id;
ALTER TABLE defense_sessions ADD COLUMN persona_ids JSON NOT NULL;
```

Migration script should convert existing rows: `persona_id = "abc"` → `persona_ids = ["abc"]`.

### Domain Entity (`backend/domain/defense_prep/entity.py`)

```python
@dataclass
class DefenseSession:
    persona_ids: list[str]  # was: persona_id: str
    # ... rest unchanged
```

### DB Model (`backend/infrastructure/models/defense_session.py`)

```python
persona_ids = Column(JSON, nullable=False)  # was: persona_id = Column(String(100))
```

### Repository Mapping

Update `_to_entity` and `_to_model` in `defense_session_repository.py` to map `persona_ids` as a list.

## API Changes

### POST `/defense-prep/sessions`

- Form parameter: `persona_ids` (comma-separated string, e.g. `"id1,id2,id3"`)
- Backend splits and validates: 1-5 items, no duplicates, all valid persona IDs
- Response field: `persona_ids: list[str]`

### Response Schema

```json
{
  "id": 1,
  "persona_ids": ["persona-ceo", "persona-cto"],
  "scenario_type": "proposal_review",
  "document_title": "Q2 Report",
  "status": "preparing",
  "question_strategy": {
    "questions": [
      {
        "question": "ROI预期是多少？",
        "dimension": "business_value",
        "difficulty": "advanced",
        "expected_direction": "...",
        "asked_by": "persona-ceo"
      }
    ]
  }
}
```

## Question Generation (Core Change)

### PlannedQuestion — new field

```python
@dataclass
class PlannedQuestion:
    question: str
    dimension: str
    difficulty: str
    expected_direction: str
    asked_by: str  # NEW: persona_id of who asks this question
```

### Generation Flow

```python
async def _generate_strategy(self, session):
    personas = [self._persona_loader.get_persona(pid) for pid in session.persona_ids]
    n = len(personas)
    questions_per_persona = max(3, 12 // n)

    all_questions = []
    for persona in personas:
        questions = await self._generate_for_persona(persona, session, count=questions_per_persona)
        for q in questions:
            q.asked_by = persona.id
        all_questions.extend(questions)

    return self._interleave_by_dimension(all_questions)
```

### Interleave Strategy

Group questions by dimension, then round-robin across personas within each group. This ensures the conversation flows naturally by topic while alternating speakers.

## Chat Session Start

```python
# Room name shows all persona names
persona_names = ", ".join(p.name for p in personas)
room = await self._chatroom_service.create_room(
    CreateChatRoomDTO(
        name=f"答辩: {persona_names}",
        type="defense",
        persona_ids=session.persona_ids
    )
)

# First question sent by the corresponding persona
first_q = strategy.questions[0]
await uow.stakeholder_message_repository.create(Message(
    sender_type="persona",
    sender_id=first_q.asked_by,
    content=first_q.question
))
```

## Frontend Changes

### State

```typescript
// was: selectedPersonaId: string
selectedPersonaIds: string[]  // max 5
```

### UI

Replace single-select dropdown with multi-select dropdown (checkbox list with selected count display).

### API Service

```typescript
export interface DefenseSession {
  persona_ids: string[]  // was: persona_id: string
  // ... rest unchanged
}

export async function createDefenseSession(
  file: File,
  personaIds: string[],  // was: personaId: string
  scenarioType: string
): Promise<DefenseSession> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('persona_ids', personaIds.join(','))
  formData.append('scenario_type', scenarioType)
  // ...
}
```

## Files to Modify

1. `backend/infrastructure/models/defense_session.py` — DB model
2. `backend/domain/defense_prep/entity.py` — Domain entity
3. `backend/domain/defense_prep/value_objects.py` — PlannedQuestion `asked_by` field
4. `backend/infrastructure/repositories/defense_session_repository.py` — Mapping
5. `backend/api/routes/defense_prep.py` — API parameter + validation
6. `backend/application/services/defense_prep_service.py` — Multi-persona question generation
7. `backend/alembic/versions/` — New migration script
8. `frontend/src/services/api.ts` — TS types + API call
9. `frontend/src/pages/DefensePrepPage.tsx` — Multi-select UI
10. `frontend/src/pages/DefensePrepPage.css` — Multi-select styles
