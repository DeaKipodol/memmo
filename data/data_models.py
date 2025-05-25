from typing import Optional, Dict, List, Any
from pydantic import BaseModel

class WritingRequirements(BaseModel):
    purpose_background: Optional[str] = None
    context_topic: Optional[str] = None
    audience_scope: Optional[str] = None
    format_structure: Optional[str] = None
    logic_evidence: Optional[str] = None
    expression_method: Optional[str] = None
    additional_constraints: Optional[str] = None
    output_expectations: Optional[str] = None

class CoTStrategyPlan(BaseModel):
    writing_type: Optional[str] = None  # 글의 유형 (예: 자기소개서, 제안서 등)
    core_message: Optional[str] = None  # 글의 중심 메시지 또는 주장
    target_audience_insight: Optional[str] = None  # 독자에 대한 해석과 고려사항
    tone_and_manner: Optional[str] = None  # 문체와 어조 (예: 진중한 1인칭, 대화체 등)
    constraints_to_observe: Optional[List[str]] = None  # 분량 제한, 금기어 등 작성 제약 조건

    # 핵심: 요구사항 필드를 어떻게 구조화할지에 대한 계획 및 구성 전략
    section_plan: List[Dict[str, Any]]  # 각 섹션별 필드 배치와 작성 전략을 포함하는 구조화된 계획
    # 각 항목 구조 예시:
    # {
    #   "section_name": "introduction",
    #   "purpose_or_goal": "글의 목적 소개 및 독자 주목 유도",
    #   "relevant_requirements_fields": ["purpose_background", "audience_scope"],
    #   "writing_guideline_or_flow": "간결한 배경 요약 후 독자의 고민을 유도하는 질문"
    # }
class AgentState(BaseModel):
    """
    LangGraph 에이전트의 전체 작업 흐름 동안 공유되고 업데이트되는 상태를 정의하는 Pydantic 모델입니다.
        """
    # 입력 및 기본 정보
    requirements: WritingRequirements   # 사용자의 8가지 글쓰기 요구사항 (가장 최신 상태)

    # 전략 수립 단계 결과물
    generated_strategy_plan: Optional[CoTStrategyPlan] = None # CoT_StrategyGeneratorNode에서 생성된 작문 전략 계획

    # 초안 작성 및 수정 단계 결과물
    current_draft_text: Optional[str] = None  # 현재 작성/수정 중인 글의 초안
    draft_metadata: Optional[List[Dict[str, Any]]] = [] # 초안의 각 부분(문단 등)이 어떤 전략/필드에 기반했는지 등의 메타데이터

    # 검토 및 피드백 단계 결과물
    review_status: Optional[str] = None  # 검토 결과 상태 (예: "approved", "needs_revision", "clarification_needed")
    feedback_for_refinement: Optional[str] = None # 검토 결과, 구체적인 수정/보완 지침

    # 최종 결과물 (한 번의 반복 또는 전체 프로세스 완료 시)
    final_iteration_output: Optional[Dict[str, str]] = None # 한 사이클의 최종 글과 다음 전략을 위한 프롬프트
                                                            # 예: {"final_text": "완성된 글...", "next_strategy_prompt": "이 글의 전략 요약..."}

    # 에이전트 운영 관련 상태
    error_message: Optional[str] = None  # 작업 중 발생한 오류 메시지
    current_operation_step: Optional[str] = None  # 현재 에이전트가 수행 중인 주요 작업 단계 (로깅/디버깅용)
    iteration_count: int = 0  # 검토 및 수정 반복 횟수 카운트