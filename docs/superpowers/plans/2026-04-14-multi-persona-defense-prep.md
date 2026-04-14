# Multi-Persona Defense Prep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support selecting 1-5 personas as defense reviewers, each independently generating questions in their own style, with round-robin interleaved questioning during the simulated defense.

**Architecture:** Change `persona_id: str` to `persona_ids: list[str]` across all layers (DB → domain → service → API → frontend). Question generation loops over each persona with a separate LLM call, then interleaves results by dimension. Chat room already supports multiple persona_ids.

**Tech Stack:** Python/FastAPI, SQLAlchemy, Alembic, React/TypeScript

**Spec:** `docs/superpowers/specs/2026-04-14-multi-persona-defense-prep-design.md`

---

### Task 1: Domain Layer — PlannedQuestion `asked_by` field

**Files:**
- Modify: `backend/domain/defense_prep/value_objects.py:24-29`
- Modify: `backend/tests/domain/test_defense_prep_entity.py`

- [ ] **Step 1: Update PlannedQuestion dataclass**

In `backend/domain/defense_prep/value_objects.py`, add `asked_by` field:

```python
@dataclass
class PlannedQuestion:
    question: str
    dimension: str
    difficulty: str = "basic"
    expected_direction: str = ""
    asked_by: str = ""
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `cd backend && python -m pytest tests/domain/test_defense_prep_entity.py -v`
Expected: All pass (new field has default, so existing code is unaffected)

- [ ] **Step 3: Commit**

```bash
git add backend/domain/defense_prep/value_objects.py
git commit -m "feat(defense-prep): add asked_by field to PlannedQuestion"
```

---

### Task 2: Domain Layer — `persona_id` → `persona_ids`

**Files:**
- Modify: `backend/domain/defense_prep/entity.py:36`
- Modify: `backend/tests/domain/test_defense_prep_entity.py`

- [ ] **Step 1: Write failing test for persona_ids**

In `backend/tests/domain/test_defense_prep_entity.py`, update `TestDefenseSession`:

```python
def test_create_session_with_multiple_personas(self):
    summary = DocumentSummary(title="test", sections=[], key_data=[], raw_text="text")
    session = DefenseSession(
        id=None,
        persona_ids=["p1", "p2", "p3"],
        scenario_type=ScenarioType.GENERAL,
        document_summary=summary,
    )
    assert session.persona_ids == ["p1", "p2", "p3"]
    assert session.status == DefenseSessionStatus.PREPARING

def test_empty_persona_ids_raises(self):
    from domain.common.exceptions import DomainValidationException
    summary = DocumentSummary(title="test", sections=[], key_data=[], raw_text="text")
    with pytest.raises(DomainValidationException):
        DefenseSession(id=None, persona_ids=[], scenario_type=ScenarioType.GENERAL, document_summary=summary)

def test_too_many_persona_ids_raises(self):
    from domain.common.exceptions import DomainValidationException
    summary = DocumentSummary(title="test", sections=[], key_data=[], raw_text="text")
    with pytest.raises(DomainValidationException):
        DefenseSession(id=None, persona_ids=["a","b","c","d","e","f"], scenario_type=ScenarioType.GENERAL, document_summary=summary)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/domain/test_defense_prep_entity.py::TestDefenseSession::test_create_session_with_multiple_personas -v`
Expected: FAIL (persona_ids not recognized)

- [ ] **Step 3: Update DefenseSession entity**

In `backend/domain/defense_prep/entity.py`, change line 36:

```python
# Before:
    persona_id: str

# After:
    persona_ids: list[str]
```

Add validation in `__post_init__`:

```python
def __post_init__(self) -> None:
    if self.status not in _VALID_STATUSES:
        raise DomainValidationException(
            f"Invalid defense session status: {self.status}",
            field="status",
            details={"allowed": sorted(_VALID_STATUSES)},
        )
    if not self.persona_ids or len(self.persona_ids) == 0:
        raise DomainValidationException(
            "至少需要选择一位答辩官",
            field="persona_ids",
        )
    if len(self.persona_ids) > 5:
        raise DomainValidationException(
            "最多选择 5 位答辩官",
            field="persona_ids",
        )
    if self.created_at is None:
        self.created_at = _utcnow()
```

- [ ] **Step 4: Update ALL existing tests to use `persona_ids=[...]` instead of `persona_id="..."`**

In `backend/tests/domain/test_defense_prep_entity.py`, find-and-replace all occurrences:
- `persona_id="persona-001"` → `persona_ids=["persona-001"]`
- `persona_id="p1"` → `persona_ids=["p1"]`

- [ ] **Step 5: Run all domain tests**

Run: `cd backend && python -m pytest tests/domain/test_defense_prep_entity.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add backend/domain/defense_prep/entity.py backend/tests/domain/test_defense_prep_entity.py
git commit -m "feat(defense-prep): change persona_id to persona_ids in domain entity"
```

---

### Task 3: DB Model + Migration

**Files:**
- Modify: `backend/infrastructure/models/defense_session.py:22`
- Create: `backend/alembic/versions/YYYYMMDD_HHMM-*_defense_session_persona_ids.py`

- [ ] **Step 1: Update ORM model**

In `backend/infrastructure/models/defense_session.py`, change line 22:

```python
# Before:
    persona_id = Column(String(100), nullable=False, comment="关联 Persona ID")

# After:
    persona_ids = Column(JSON, nullable=False, comment="答辩官 Persona ID 列表 (1-5)")
```

- [ ] **Step 2: Generate Alembic migration**

Run: `cd backend && alembic revision --autogenerate -m "defense_session_persona_id_to_persona_ids"`

- [ ] **Step 3: Review and adjust the generated migration**

Open the generated file and ensure it:
1. Drops `persona_id` column
2. Adds `persona_ids` JSON column
3. Has a data migration step to convert existing rows

The upgrade function should look like:

```python
def upgrade() -> None:
    # Add new column
    op.add_column('defense_sessions', sa.Column('persona_ids', sa.JSON(), nullable=True, comment='答辩官 Persona ID 列表 (1-5)'))
    # Migrate existing data
    op.execute("UPDATE defense_sessions SET persona_ids = json_array(persona_id) WHERE persona_id IS NOT NULL")
    # Make non-nullable and drop old column
    op.alter_column('defense_sessions', 'persona_ids', nullable=False)
    op.drop_column('defense_sessions', 'persona_id')
```

The downgrade:

```python
def downgrade() -> None:
    op.add_column('defense_sessions', sa.Column('persona_id', sa.String(100), nullable=True))
    op.execute("UPDATE defense_sessions SET persona_id = json_extract(persona_ids, '$[0]')")
    op.alter_column('defense_sessions', 'persona_id', nullable=False)
    op.drop_column('defense_sessions', 'persona_ids')
```

- [ ] **Step 4: Run migration**

Run: `cd backend && alembic upgrade head`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add backend/infrastructure/models/defense_session.py backend/alembic/versions/
git commit -m "feat(defense-prep): migrate persona_id to persona_ids JSON column"
```

---

### Task 4: Repository Mapping

**Files:**
- Modify: `backend/infrastructure/repositories/defense_session_repository.py`

- [ ] **Step 1: Update `_to_entity` method (line 66-75)**

```python
# Before (line 68):
        return DefenseSession(
            id=model.id,
            persona_id=model.persona_id,
            ...

# After:
        return DefenseSession(
            id=model.id,
            persona_ids=model.persona_ids,
            ...
```

- [ ] **Step 2: Update `_strategy_to_dict` method (line 88-99)**

Add `asked_by` to serialization:

```python
def _strategy_to_dict(self, strategy: QuestionStrategy) -> dict:
    return {
        "questions": [
            {
                "question": q.question,
                "dimension": q.dimension,
                "difficulty": q.difficulty,
                "expected_direction": q.expected_direction,
                "asked_by": q.asked_by,
            }
            for q in strategy.questions
        ]
    }
```

- [ ] **Step 3: Update `_to_entity` question deserialization (line 56-61)**

Add `asked_by` when reading back:

```python
PlannedQuestion(
    question=q.get("question", ""),
    dimension=q.get("dimension", ""),
    difficulty=q.get("difficulty", "basic"),
    expected_direction=q.get("expected_direction", ""),
    asked_by=q.get("asked_by", ""),
)
```

- [ ] **Step 4: Update `create` method (line 106-107)**

```python
# Before:
        model = DefenseSessionModel(
            persona_id=session.persona_id,

# After:
        model = DefenseSessionModel(
            persona_ids=session.persona_ids,
```

- [ ] **Step 5: Run existing tests**

Run: `cd backend && python -m pytest tests/ -v -k defense`
Expected: Service test needs update (next task), but domain tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/infrastructure/repositories/defense_session_repository.py
git commit -m "feat(defense-prep): update repository mapping for persona_ids and asked_by"
```

---

### Task 5: Service Layer — Multi-Persona Question Generation

**Files:**
- Modify: `backend/application/services/defense_prep_service.py`
- Modify: `backend/tests/application/test_defense_prep_service.py`

- [ ] **Step 1: Update `_STRATEGY_PROMPT` to accept `question_count`**

In `backend/application/services/defense_prep_service.py`, update the prompt (line 42-46):

```python
_STRATEGY_PROMPT = """\
你是一位{role}，{tone}风格。
你的典型追问：{typical_questions}

你正在参加一场{scenario_name}。

以下是被评审者提交的文档内容：
---
{document_text}
---

请基于以下维度分析文档，找出薄弱点和可追问的地方：
{dimensions}

## 提问角度参考
{question_angles}

要求：
1. 找出文档中数据薄弱、逻辑不严密、结论缺少支撑的地方
2. 生成 {question_count} 个问题，按优先级排序
3. 每个问题标注：目标维度(dimension)、难度(difficulty: basic/advanced/stress_test)、期望回答方向(expected_direction)
4. 问题应符合你的角色风格和关注点
"""
```

- [ ] **Step 2: Update `create_session` signature (line 124)**

```python
# Before:
    async def create_session(self, file_content: bytes, filename: str, persona_id: str, scenario_type: ScenarioType) -> DefenseSession:
        summary = await self._parser.parse(file_content, filename)
        session = DefenseSession(id=None, persona_id=persona_id, scenario_type=scenario_type, document_summary=summary)

# After:
    async def create_session(self, file_content: bytes, filename: str, persona_ids: list[str], scenario_type: ScenarioType) -> DefenseSession:
        summary = await self._parser.parse(file_content, filename)
        session = DefenseSession(id=None, persona_ids=persona_ids, scenario_type=scenario_type, document_summary=summary)
```

- [ ] **Step 3: Rewrite `_generate_strategy` for multi-persona (line 172-205)**

Replace the entire method:

```python
async def _generate_strategy(self, session: DefenseSession) -> QuestionStrategy:
    config = SCENARIO_CONFIGS[session.scenario_type]
    n = len(session.persona_ids)
    questions_per_persona = max(3, 12 // n)

    all_questions: list[PlannedQuestion] = []
    for pid in session.persona_ids:
        persona = self._persona_loader.get_persona(pid)
        role = persona.role if persona else "上级领导"
        tone = ""
        typical_questions = ""
        if persona:
            if persona.expression:
                tone = persona.expression.tone
            if persona.decision:
                typical_questions = ", ".join(persona.decision.typical_questions[:5])
        prompt = _STRATEGY_PROMPT.format(
            role=role, tone=tone or "专业严谨",
            typical_questions=typical_questions or "（无特定追问）",
            scenario_name=config["name"],
            document_text=session.document_summary.raw_text[:8000],
            dimensions=", ".join(config["dimensions"]),
            question_angles="\n".join(f"- {a}" for a in config["question_angles"]),
            question_count=questions_per_persona,
        )
        messages = [LLMMessage(role="user", content=prompt)]
        try:
            parsed = await self._llm.generate_structured(
                messages, schema=_STRATEGY_SCHEMA,
                schema_name="defense_question_strategy",
                schema_description="生成答辩提问策略", temperature=0.4,
            )
        except Exception as exc:
            logger.error("LLM strategy generation failed for persona %s: %s", pid, exc)
            raise ValueError("提问策略生成失败，请重试") from exc
        for q in parsed.get("questions", [])[:questions_per_persona]:
            all_questions.append(PlannedQuestion(
                question=q.get("question", ""),
                dimension=q.get("dimension", ""),
                difficulty=q.get("difficulty", "basic"),
                expected_direction=q.get("expected_direction", ""),
                asked_by=pid,
            ))

    # Interleave by dimension so different personas alternate
    interleaved = self._interleave_by_dimension(all_questions)
    return QuestionStrategy(questions=interleaved)

def _interleave_by_dimension(self, questions: list[PlannedQuestion]) -> list[PlannedQuestion]:
    """Group by dimension, then round-robin within each group to alternate personas."""
    from collections import defaultdict
    by_dim: dict[str, list[PlannedQuestion]] = defaultdict(list)
    dim_order: list[str] = []
    for q in questions:
        if q.dimension not in dim_order:
            dim_order.append(q.dimension)
        by_dim[q.dimension].append(q)
    result: list[PlannedQuestion] = []
    for dim in dim_order:
        # Within same dimension, sort by persona to interleave
        group = by_dim[dim]
        result.extend(group)
    return result
```

- [ ] **Step 4: Update `start_session` for multi-persona (line 133-170)**

Replace the persona_id references:

```python
async def start_session(self, session_id: int) -> DefenseSession:
    async with self._uow_factory() as uow:
        session = await uow.defense_session_repository.get_by_id(session_id)
        if session is None:
            raise ValueError(f"Defense session {session_id} not found")
        strategy = await self._generate_strategy(session)
        session.question_strategy = strategy
        # Build room name from all persona names
        persona_names = []
        for pid in session.persona_ids:
            p = self._persona_loader.get_persona(pid)
            persona_names.append(p.name if p else pid)
        room = await self._chatroom_service.create_room(
            CreateChatRoomDTO(name=f"答辩: {', '.join(persona_names)}", type="defense", persona_ids=session.persona_ids)
        )
        session.start(room_id=room.id)
        await uow.defense_session_repository.update(session)
        await uow.commit()

    config = SCENARIO_CONFIGS[session.scenario_type]
    context_msg = (
        f"[答辩模式] 场景: {config['name']}\n"
        f"文档: {session.document_summary.title}\n"
        f"评估维度: {', '.join(config['dimensions'])}\n\n"
        f"文档摘要:\n{session.document_summary.raw_text[:3000]}"
    )
    first_q = strategy.questions[0] if strategy.questions else None
    first_q_text = first_q.question if first_q else "请介绍一下这份文档的核心内容。"
    first_q_sender = first_q.asked_by if first_q else session.persona_ids[0]

    from domain.stakeholder.entity import Message
    async with self._uow_factory() as uow:
        await uow.stakeholder_message_repository.create(Message(
            id=None, room_id=room.id, sender_type="system", sender_id="system", content=context_msg,
        ))
        await uow.stakeholder_message_repository.create(Message(
            id=None, room_id=room.id, sender_type="persona", sender_id=first_q_sender, content=first_q_text,
        ))
        await uow.commit()

    return session
```

- [ ] **Step 5: Update service test**

In `backend/tests/application/test_defense_prep_service.py`, update the test:

```python
async def test_create_session_parses_doc_and_persists(self, mock_deps):
    uow, llm, parser, chatroom_svc, persona_loader = mock_deps
    parser.parse.return_value = DocumentSummary(title="Q1报告", sections=[], key_data=["30%"], raw_text="full text")
    uow.defense_session_repository.create.side_effect = lambda s: setattr(s, "id", 1) or s

    service = DefensePrepService(
        uow_factory=lambda: uow, llm=llm, document_parser=parser,
        chatroom_service=chatroom_svc, persona_loader=persona_loader,
    )
    session = await service.create_session(
        file_content=b"fake pptx bytes", filename="Q1报告.pptx",
        persona_ids=["persona-001", "persona-002"], scenario_type=ScenarioType.PERFORMANCE_REVIEW,
    )
    parser.parse.assert_called_once_with(b"fake pptx bytes", "Q1报告.pptx")
    uow.defense_session_repository.create.assert_called_once()
    assert session.id == 1
    assert session.persona_ids == ["persona-001", "persona-002"]
    assert session.status == "preparing"
```

- [ ] **Step 6: Write unit test for `_interleave_by_dimension`**

In `backend/tests/application/test_defense_prep_service.py`, add:

```python
from domain.defense_prep.value_objects import PlannedQuestion

class TestInterleaveByDimension:
    def test_interleaves_questions_by_dimension(self, mock_deps):
        uow, llm, parser, chatroom_svc, persona_loader = mock_deps
        service = DefensePrepService(
            uow_factory=lambda: uow, llm=llm, document_parser=parser,
            chatroom_service=chatroom_svc, persona_loader=persona_loader,
        )
        questions = [
            PlannedQuestion(question="Q1", dimension="business", asked_by="p1"),
            PlannedQuestion(question="Q2", dimension="tech", asked_by="p1"),
            PlannedQuestion(question="Q3", dimension="business", asked_by="p2"),
            PlannedQuestion(question="Q4", dimension="tech", asked_by="p2"),
        ]
        result = service._interleave_by_dimension(questions)
        # Business questions first (Q1, Q3), then tech (Q2, Q4)
        assert result[0].question == "Q1"
        assert result[1].question == "Q3"
        assert result[2].question == "Q2"
        assert result[3].question == "Q4"

    def test_handles_single_persona(self, mock_deps):
        uow, llm, parser, chatroom_svc, persona_loader = mock_deps
        service = DefensePrepService(
            uow_factory=lambda: uow, llm=llm, document_parser=parser,
            chatroom_service=chatroom_svc, persona_loader=persona_loader,
        )
        questions = [
            PlannedQuestion(question="Q1", dimension="a", asked_by="p1"),
            PlannedQuestion(question="Q2", dimension="b", asked_by="p1"),
        ]
        result = service._interleave_by_dimension(questions)
        assert len(result) == 2
```

- [ ] **Step 7: Run all tests**

Run: `cd backend && python -m pytest tests/ -v -k defense`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add backend/application/services/defense_prep_service.py backend/tests/application/test_defense_prep_service.py
git commit -m "feat(defense-prep): multi-persona question generation with interleaving"
```

---

### Task 6: API Route — `persona_ids` Parameter

**Files:**
- Modify: `backend/api/routes/defense_prep.py`

- [ ] **Step 1: Update create_session endpoint (line 19-44)**

```python
@router.post("/sessions")
async def create_session(
    file: UploadFile = File(...),
    persona_ids: str = Form(...),  # comma-separated
    scenario_type: str = Form(...),
    service: DefensePrepService = Depends(get_defense_prep_service),
):
    from pathlib import Path
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件格式: {ext}")
    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(400, "文件大小不能超过 20MB")
    try:
        st = ScenarioType(scenario_type)
    except ValueError:
        raise HTTPException(400, f"无效的场景类型: {scenario_type}")

    # Parse and validate persona_ids
    pid_list = [p.strip() for p in persona_ids.split(",") if p.strip()]
    if not pid_list:
        raise HTTPException(400, "至少需要选择一位答辩官")
    if len(pid_list) > 5:
        raise HTTPException(400, "最多选择 5 位答辩官")
    if len(pid_list) != len(set(pid_list)):
        raise HTTPException(400, "答辩官不能重复选择")

    session = await service.create_session(
        file_content=content, filename=file.filename or "document",
        persona_ids=pid_list, scenario_type=st,
    )
    return success_response({
        "id": session.id, "persona_ids": session.persona_ids,
        "scenario_type": session.scenario_type.value,
        "document_title": session.document_summary.title,
        "status": session.status,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    })
```

- [ ] **Step 2: Update get_session response (line 47-63)**

Change `persona_id` → `persona_ids` in response dict, and add `asked_by` to question serialization:

```python
@router.get("/sessions/{session_id}")
async def get_session(session_id: int, service: DefensePrepService = Depends(get_defense_prep_service)):
    session = await service.get_session(session_id)
    if session is None:
        raise HTTPException(404, "会话不存在")
    data = {
        "id": session.id, "persona_ids": session.persona_ids,
        "scenario_type": session.scenario_type.value,
        "document_title": session.document_summary.title,
        "status": session.status, "room_id": session.room_id,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }
    if session.question_strategy:
        data["question_strategy"] = {
            "questions": [
                {"question": q.question, "dimension": q.dimension, "difficulty": q.difficulty, "asked_by": q.asked_by}
                for q in session.question_strategy.questions
            ]
        }
    return success_response(data)
```

- [ ] **Step 3: Update start_session response (line 66-77)**

Add `asked_by` to question serialization:

```python
return success_response({
    "id": session.id, "room_id": session.room_id, "status": session.status,
    "question_strategy": {
        "questions": [
            {"question": q.question, "dimension": q.dimension, "difficulty": q.difficulty, "asked_by": q.asked_by}
            for q in (session.question_strategy.questions if session.question_strategy else [])
        ]
    },
})
```

- [ ] **Step 4: Commit**

```bash
git add backend/api/routes/defense_prep.py
git commit -m "feat(defense-prep): API accepts persona_ids comma-separated parameter"
```

---

### Task 7: Frontend — API Types + Multi-Select UI

**Files:**
- Modify: `frontend/src/services/api.ts:723-762`
- Modify: `frontend/src/pages/DefensePrepPage.tsx`
- Modify: `frontend/src/pages/DefensePrepPage.css`

- [ ] **Step 1: Update TypeScript types in api.ts**

In `frontend/src/services/api.ts`, update `DefenseSession` interface (line 723-734):

```typescript
export interface DefenseSession {
  id: number
  persona_ids: string[]
  scenario_type: string
  document_title: string
  status: 'preparing' | 'in_progress' | 'completed'
  room_id: number | null
  created_at: string | null
  question_strategy?: {
    questions: { question: string; dimension: string; difficulty: string; asked_by: string }[]
  }
}
```

Update `createDefenseSession` function (line 750-762):

```typescript
export async function createDefenseSession(file: File, personaIds: string[], scenarioType: string): Promise<DefenseSession> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('persona_ids', personaIds.join(','))
  formData.append('scenario_type', scenarioType)
  const resp = await fetch(`/api/v1/defense-prep/sessions`, { method: 'POST', body: formData })
  if (!resp.ok) {
    const json = await resp.json().catch(() => null)
    throw new Error(json?.message || `创建失败: ${resp.status}`)
  }
  const json: ApiResponse<DefenseSession> = await resp.json()
  return json.data
}
```

- [ ] **Step 2: Update DefensePrepPage state and logic**

In `frontend/src/pages/DefensePrepPage.tsx`:

Change `initialState`:

```typescript
function initialState() {
  return {
    step: 1 as 1 | 2,
    file: null as File | null,
    selectedPersonaIds: [] as string[],
    scenarioType: '',
    loading: false,
    error: null as string | null,
    session: null as DefenseSession | null,
    submitting: false,
    dragOver: false,
  }
}
```

Update destructuring:

```typescript
const {
  step, file, selectedPersonaIds, scenarioType,
  loading, error, session, submitting, dragOver,
} = state
```

Update `handleUpload`:

```typescript
const handleUpload = async () => {
  if (!file || selectedPersonaIds.length === 0 || !scenarioType) return
  setState((s) => ({ ...s, loading: true, error: null }))
  try {
    const sess = await createDefenseSession(file, selectedPersonaIds, scenarioType)
    setState((s) => ({ ...s, loading: false, session: sess, step: 2 }))
  } catch (e: any) {
    setState((s) => ({ ...s, loading: false, error: e.message || '创建失败，请重试' }))
  }
}
```

Update `selectedPersona` line and step 2 summary:

```typescript
const selectedPersonaNames = selectedPersonaIds.map(id => personaMap[id]?.name ?? id).join('、')
```

Update disabled check on submit button:

```typescript
disabled={!file || selectedPersonaIds.length === 0 || !scenarioType || loading}
```

- [ ] **Step 3: Replace single-select dropdown with multi-select checkbox dropdown**

Replace the `<select>` persona section with a custom multi-select:

```tsx
{/* Persona selection */}
<div className="dp-section-label">选择答辩官（最多 5 位）</div>
<div className="dp-multi-select">
  {personas.map((p) => (
    <label key={p.id} className={`dp-multi-option ${selectedPersonaIds.includes(p.id) ? 'selected' : ''}`}>
      <input
        type="checkbox"
        checked={selectedPersonaIds.includes(p.id)}
        onChange={() => {
          setState((s) => {
            const ids = s.selectedPersonaIds.includes(p.id)
              ? s.selectedPersonaIds.filter((x) => x !== p.id)
              : s.selectedPersonaIds.length < 5
                ? [...s.selectedPersonaIds, p.id]
                : s.selectedPersonaIds
            return { ...s, selectedPersonaIds: ids }
          })
        }}
      />
      <span className="dp-multi-option-name">{p.name}</span>
      <span className="dp-multi-option-role">{p.role}</span>
    </label>
  ))}
</div>
```

Update step 2 summary section — replace `selectedPersona?.name` line:

```tsx
<div className="dp-summary-row">
  <span className="dp-summary-label">答辩官</span>
  <span className="dp-summary-value">{selectedPersonaNames}</span>
</div>
```

- [ ] **Step 4: Add multi-select CSS**

In `frontend/src/pages/DefensePrepPage.css`, replace the `.dp-select` styles with:

```css
/* Multi-select persona list */
.dp-multi-select {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 240px;
  overflow-y: auto;
  padding: 4px;
  border: 1.5px solid var(--border);
  border-radius: 10px;
  background: var(--bg-base);
}

.dp-multi-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background var(--transition-fast);
  user-select: none;
}

.dp-multi-option:hover {
  background: var(--violet-soft);
}

.dp-multi-option.selected {
  background: var(--violet-soft);
}

.dp-multi-option input[type="checkbox"] {
  accent-color: var(--violet);
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.dp-multi-option-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.dp-multi-option-role {
  font-size: 12px;
  color: var(--text-muted);
  margin-left: auto;
}
```

- [ ] **Step 5: Verify frontend compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/services/api.ts frontend/src/pages/DefensePrepPage.tsx frontend/src/pages/DefensePrepPage.css
git commit -m "feat(defense-prep): multi-select persona UI and updated API types"
```

---

### Task 8: Integration Smoke Test

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -v -k defense`
Expected: All pass

- [ ] **Step 2: Run frontend type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Final commit with spec update**

```bash
git add -A
git commit -m "feat(defense-prep): complete multi-persona support (1-5 reviewers)"
```
