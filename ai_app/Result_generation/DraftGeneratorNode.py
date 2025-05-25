
import logging
from typing import List
from data.data_models import AgentState, CoTStrategyPlan, WritingRequirements
from ai_app.assist.common import client, model
import asyncio
logger = logging.getLogger(__name__)

# build_draft_prompt: 각 섹션별 LLM 프롬프트 생성
# 변경: target_audience_insight(독자 분석) 및 명확한 변수 분리 포함
def build_draft_prompt(section: dict,requirements: WritingRequirements,strategy: CoTStrategyPlan) -> str:
    """각 섹션별 LLM 프롬프트 생성 (target_audience_insight 포함)"""
    # 섹션 기본 정보
    section_name = section.get('section_name', '')
    purpose = section.get('purpose_or_goal', '')
    guideline = section.get('writing_guideline_or_flow', '')

    # 관련 요구사항 필드 내용 추출
    context_fields = section.get('relevant_requirements_fields', [])
    context_snippets = {
        field: getattr(requirements, field)
        for field in context_fields
        if getattr(requirements, field, None)
    }
    req_context = '\n'.join(f'- {k}: {v}' for k, v in context_snippets.items())

    # 제약조건 목록
    constraints = '\n'.join(f'- {c}' for c in strategy.constraints_to_observe)

    # target_audience_insight 추가 (독자 분석)
    audience_insight = strategy.target_audience_insight or ''

    # 전체 전략 정보 구성
    strategy_info = (
        f"- 글쓰기 유형: {strategy.writing_type}\n"
        f"- 핵심 메시지: {strategy.core_message}\n"
        f"- 독자 분석: {audience_insight}\n"
        f"- 톤앤매너: {strategy.tone_and_manner}\n"
        f"- 제약조건:\n{constraints}"
    )

    # 최종 프롬프트 문자열
    return f"""
[System]
당신은 전략적 글쓰기 전문가입니다. 아래 지침에 따라 자기소개서 '{section_name}' 섹션을 작성하세요.

[섹션 이름]: {section_name}
[섹션 목적]: {purpose}
[작성 지침]: {guideline}

[관련 요구사항 필드]:
{req_context}

[전체 전략 정보]
{strategy_info}

위 정보를 바탕으로 해당 섹션 내용을 순수 텍스트로, 마크다운 없이, 한글로 작성하세요.
""".strip()

# generate_draft_section: LLM 호출을 통해 섹션별 초안 생성
# 변경: system/user 메시지 분리, 예외 처리 로깅 추가
# generate_draft_section을 async 함수로 변경
# 기존 async def 제거 및 동기 방식으로 수정
from concurrent.futures import ThreadPoolExecutor  # 병렬 처리 추가

def generate_draft_section(section: dict, requirements: WritingRequirements, strategy: CoTStrategyPlan) -> str:
    """LLM 호출을 통해 섹션별 초안 생성 (동기)"""
    prompt = build_draft_prompt(section, requirements, strategy)
    try:
        response = client.responses.create(  # 동기 호출로 변경
            model=model.advanced,
            input=[
                {'role': 'system', 'content': '당신은 전략적 글쓰기 전문가입니다. 섹션 초안만 출력하세요.'},
                {'role': 'user', 'content': prompt},
            ],
            text={'format': {'type': 'text'}},
        )
        return response.output_text
    except Exception as e:
        logger.error(f"Draft 생성 실패 ({section.get('section_name')}): {e}")
        return f"[Error generating draft for {section.get('section_name')}]"

def draft_generator_node(state: AgentState) -> AgentState:
    """전략 기반 섹션별 초안 생성 (동기 + 병렬 처리)"""
    requirements = state.requirements
    strategy = state.generated_strategy_plan
    
    # ThreadPool을 사용한 병렬 처리
    with ThreadPoolExecutor() as executor:
        draft_results = list(executor.map(
            lambda section: generate_draft_section(section, requirements, strategy),
            strategy.section_plan
        ))
    
    draft_texts = [
        f"[{section.get('section_name')}]:\n{draft}"
        for section, draft in zip(strategy.section_plan, draft_results)
    ]
    state.current_draft_text = '\n\n'.join(draft_texts)
    return state